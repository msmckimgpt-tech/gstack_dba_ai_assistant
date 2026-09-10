"""Inspect real Windows shell properties and capture DQA taskbar buttons.

Run each surface in a separate Windows Python process:
  verify_taskbar_identity.py --src <src> --out <evidence-dir> --surface tk|webview

Only probe windows are opened/closed. No client entrypoint, AI discovery, login,
installer, or update is executed. read_window_properties(hwnd) can also inspect
an independently launched frozen test window without modifying that window.
"""
from __future__ import annotations

import argparse
import ctypes
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
import uuid


class GUID(ctypes.Structure):
    _fields_ = [("data", ctypes.c_ubyte * 16)]

    @classmethod
    def parse(cls, value):
        return cls.from_buffer_copy(uuid.UUID(value).bytes_le)


class PROPERTYKEY(ctypes.Structure):
    _fields_ = [("fmtid", GUID), ("pid", ctypes.c_uint32)]


class VALUE(ctypes.Union):
    _fields_ = [("text", ctypes.c_wchar_p),
                ("storage", ctypes.c_byte * (16 if ctypes.sizeof(ctypes.c_void_p) == 8 else 8))]


class PROPVARIANT(ctypes.Structure):
    _fields_ = [("vt", ctypes.c_ushort), ("reserved", ctypes.c_ushort * 3), ("value", VALUE)]


def _check(hr):
    if hr < 0:
        raise OSError(f"Windows HRESULT 0x{hr & 0xffffffff:08x}")


def read_process_identity():
    shell, ole = ctypes.windll.shell32, ctypes.windll.ole32
    shell.GetCurrentProcessExplicitAppUserModelID.argtypes = [ctypes.POINTER(ctypes.c_wchar_p)]
    shell.GetCurrentProcessExplicitAppUserModelID.restype = ctypes.c_long
    ole.CoTaskMemFree.argtypes = [ctypes.c_void_p]
    value = ctypes.c_wchar_p()
    hr = shell.GetCurrentProcessExplicitAppUserModelID(ctypes.byref(value))
    try:
        return {"hresult": hr, "value": value.value if hr == 0 else None}
    finally:
        if hr == 0:
            ole.CoTaskMemFree(ctypes.cast(value, ctypes.c_void_p))


def read_window_properties(hwnd):
    """Read properties 2/3/4/5 through IPropertyStore::GetValue; never set them."""
    ptr = ctypes.c_void_p
    shell, ole = ctypes.windll.shell32, ctypes.windll.ole32
    shell.SHGetPropertyStoreForWindow.argtypes = [ptr, ctypes.POINTER(GUID), ctypes.POINTER(ptr)]
    shell.SHGetPropertyStoreForWindow.restype = ctypes.c_long
    ole.PropVariantClear.argtypes = [ctypes.POINTER(PROPVARIANT)]
    iid = GUID.parse("886d8eeb-8cf2-4446-8d02-cdba1dbdcf99")
    fmtid = GUID.parse("9f4c2855-9f79-4b39-a8d0-e1d42de1d5f3")
    store = ptr()
    _check(shell.SHGetPropertyStoreForWindow(hwnd, ctypes.byref(iid), ctypes.byref(store)))
    table = ctypes.cast(store, ctypes.POINTER(ctypes.POINTER(ptr))).contents
    get_value = ctypes.WINFUNCTYPE(ctypes.c_long, ptr, ctypes.POINTER(PROPERTYKEY),
                                  ctypes.POINTER(PROPVARIANT))(table[5])
    release = ctypes.WINFUNCTYPE(ctypes.c_ulong, ptr)(table[2])
    result = {}
    try:
        for prop_id in (2, 3, 4, 5):
            key, value = PROPERTYKEY(fmtid, prop_id), PROPVARIANT()
            try:
                hr = get_value(store, ctypes.byref(key), ctypes.byref(value))
                _check(hr)
                result[str(prop_id)] = {"hresult": hr, "vt": value.vt,
                                       "value": value.value.text if value.vt == 31 else None}
            finally:
                ole.PropVariantClear(ctypes.byref(value))
    finally:
        release(store)
    return result


def is_window_visible(hwnd):
    visible = ctypes.windll.user32.IsWindowVisible
    visible.argtypes = [ctypes.c_void_p]
    visible.restype = ctypes.c_int
    return bool(visible(hwnd))


def _expected(branding):
    return {"2": branding.relaunch_command(), "3": f"{branding.ICON_PATH},0",
            "4": "DQA", "5": branding.APP_USER_MODEL_ID}


def _assert_properties(values, expected):
    for key, text in expected.items():
        assert values[key]["vt"] == 31 and values[key]["value"] == text, (key, values[key])


def _assert_cleared(values):
    assert all(value["vt"] == 0 for value in values.values()), values


def capture_taskbar(out):
    """UIA can expose only taskbar panes; the companion script also reads MSAA."""
    script = Path(__file__).with_name("capture_taskbar.ps1")
    completed = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-File", str(script),
         "-OutputDir", str(out)], capture_output=True, timeout=30)
    if completed.returncode:
        raise RuntimeError(f"Taskbar capture failed ({completed.returncode}): "
                           + completed.stderr.decode("utf-8", errors="replace"))
    captured = json.loads((out / "taskbar.json").read_text(encoding="utf-8-sig"))
    assert captured["buttonCaptures"], "No DQA/Python taskbar buttons could be captured"
    return captured


def verify_tk(branding, out, result):
    import tkinter as tk

    branding.initialize_process()
    root = tk.Tk()
    try:
        root.title("DQA taskbar verification")
        branding.bind_tk_window(root)
        root.geometry("320x100")
        root.update()
        hwnd = int(root.frame(), 0)
        result["hwnd"] = hwnd
        result["properties"] = read_window_properties(hwnd)
        _assert_properties(result["properties"], _expected(branding))
        assert is_window_visible(hwnd), "Tk window was not shown"
        result["process_identity"] = read_process_identity()
        assert result["process_identity"]["value"] == branding.APP_USER_MODEL_ID
        result["hide_show"] = []
        for _ in range(3):
            root.withdraw()
            root.update()
            hidden = read_window_properties(int(root.frame(), 0))
            _assert_properties(hidden, _expected(branding))
            hidden_visible = is_window_visible(int(root.frame(), 0))
            assert not hidden_visible, "Tk window did not hide"
            root.deiconify()
            root.update()
            shown = read_window_properties(int(root.frame(), 0))
            _assert_properties(shown, _expected(branding))
            shown_visible = is_window_visible(int(root.frame(), 0))
            assert shown_visible, "Tk window did not return"
            result["hide_show"].append({"hidden": hidden, "shown": shown,
                                        "hidden_visible": hidden_visible,
                                        "shown_visible": shown_visible})
        result["taskbar"] = capture_taskbar(out)
        branding.clear_window(int(root.frame(), 0))
        result["after_clear"] = read_window_properties(int(root.frame(), 0))
        _assert_cleared(result["after_clear"])
    finally:
        branding.clear_window(int(root.frame(), 0))
        root.destroy()


def verify_webview(branding, window, out, result):
    shell = window.Shell("about:blank", "DQA taskbar verification", str(out / "webview-profile"))
    failures, stop = [], threading.Event()

    def inspect():
        try:
            deadline = time.monotonic() + 45
            while not stop.is_set() and time.monotonic() < deadline:
                if shell._window is not None and shell._window.events.shown.wait(0.05):
                    break
                time.sleep(0.05)
            else:
                raise AssertionError("WebView2 window did not become visible")
            hwnd = int(shell._window.native.Handle.ToInt64())
            result["hwnd"] = hwnd
            result["properties"] = read_window_properties(hwnd)
            _assert_properties(result["properties"], _expected(branding))
            assert is_window_visible(hwnd), "WebView2 window was not shown"
            result["process_identity"] = read_process_identity()
            assert result["process_identity"]["value"] == branding.APP_USER_MODEL_ID
            shell.can_hide = lambda: True
            assert shell._on_closing() is False
            hidden = read_window_properties(hwnd)
            _assert_properties(hidden, _expected(branding))
            hidden_visible = is_window_visible(hwnd)
            assert not hidden_visible, "WebView2 window did not hide"
            shell.show()
            time.sleep(0.5)
            shown = read_window_properties(hwnd)
            _assert_properties(shown, _expected(branding))
            shown_visible = is_window_visible(hwnd)
            assert shown_visible, "WebView2 window did not return"
            result["hide_show"] = [{"hidden": hidden, "shown": shown,
                                    "hidden_visible": hidden_visible,
                                    "shown_visible": shown_visible}]
            result["taskbar"] = capture_taskbar(out)
            shell._quitting = True
            assert shell._on_closing() is True
            result["after_clear"] = read_window_properties(hwnd)
            _assert_cleared(result["after_clear"])
        except Exception as exc:
            failures.append(repr(exc))
        finally:
            shell.quit()

    worker = threading.Thread(target=inspect, daemon=True)
    worker.start()
    try:
        assert shell.run(), shell.last_error
    finally:
        stop.set()
        worker.join(timeout=35)
    assert not worker.is_alive(), "Taskbar inspection did not finish"
    assert not failures, failures


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--src", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--surface", choices=("tk", "webview"), required=True)
    args = parser.parse_args()
    if os.name != "nt":
        parser.error("Run this probe with Windows Python")
    args.out = args.out.resolve()
    args.out.mkdir(parents=True, exist_ok=True)
    result = {"pid": os.getpid(), "surface": args.surface, "verdict": "RUNNING",
              "visual_review": "Review captured taskbar button images separately"}
    path = args.out / "result.json"
    path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    try:
        sys.path.insert(0, str(args.src.resolve()))
        from client import branding, window

        result["initial_process_identity"] = read_process_identity()
        if args.surface == "tk":
            verify_tk(branding, args.out, result)
        else:
            verify_webview(branding, window, args.out, result)
        result["verdict"] = "PASS"
    except Exception as exc:
        result.update(verdict="FAIL", error=repr(exc))
        raise
    finally:
        path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
