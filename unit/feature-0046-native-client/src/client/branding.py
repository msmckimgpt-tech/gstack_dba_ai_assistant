"""Windows shell identity and icons for source runs and installed bundles."""
from __future__ import annotations

import ctypes
import logging
import os
from pathlib import Path
import subprocess
import sys
import uuid

ICON_PATH = Path(__file__).resolve().parent / "assets" / "dqa.ico"
APP_USER_MODEL_ID = "Masangsoft.DQA.Connect"
_LOG = logging.getLogger(__name__)


def initialize_process() -> None:
    """Set identity before any UI so Windows does not group DQA under Python."""
    if os.name != "nt":
        return
    try:
        setter = ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID
        setter.argtypes = [ctypes.c_wchar_p]
        setter.restype = ctypes.c_long
        _check(setter(APP_USER_MODEL_ID))
    except (OSError, AttributeError) as exc:
        _LOG.warning("Could not set DQA taskbar identity: %s", exc)


def relaunch_command() -> str:
    # Startup arguments can contain a delegated token. Never persist them in shell metadata.
    if getattr(sys, "frozen", False):
        return subprocess.list2cmdline([sys.executable])
    python = Path(sys.executable)
    windowless = python.with_name("pythonw.exe")
    if os.name == "nt" and windowless.is_file():
        python = windowless
    return subprocess.list2cmdline([str(python), str(ICON_PATH.parents[2] / "dqa_connect.py")])


def _check(result: int) -> None:
    if result < 0:
        raise OSError(f"Windows shell HRESULT 0x{result & 0xffffffff:08x}")


def configure_window(hwnd: int) -> None:
    """Give the taskbar group and newly pinned shortcut an explicit icon and target."""
    if os.name != "nt":
        return
    try:
        _set_window_properties(hwnd, (
            (2, relaunch_command()),
            (3, f"{ICON_PATH},0"),
            (4, "DQA"),
            (5, APP_USER_MODEL_ID),  # Setting ID last refreshes the taskbar metadata.
        ))
    except (OSError, AttributeError) as exc:
        _LOG.warning("Could not set DQA window taskbar properties: %s", exc)


def clear_window(hwnd: int) -> None:
    """Release shell-owned property values before destroying the HWND."""
    if os.name == "nt":
        try:
            _set_window_properties(hwnd, tuple((key, None) for key in (2, 3, 4, 5)))
        except (OSError, AttributeError) as exc:
            _LOG.warning("Could not clear DQA window taskbar properties: %s", exc)


def bind_tk_window(root) -> None:
    if os.name == "nt":
        root.iconbitmap(default=str(ICON_PATH))

        def mapped(event):
            # Tk may replace its wrapper HWND during the first map or a later remap.
            if event.widget is root:
                configure_window(int(root.frame(), 0))

        root.bind("<Map>", mapped, add="+")


def _set_window_properties(hwnd: int, properties: tuple) -> None:
    class GUID(ctypes.Structure):
        _fields_ = [("data", ctypes.c_ubyte * 16)]

        @classmethod
        def parse(cls, value):
            return cls.from_buffer_copy(uuid.UUID(value).bytes_le)

    class PROPERTYKEY(ctypes.Structure):
        _fields_ = [("fmtid", GUID), ("pid", ctypes.c_uint32)]

    class Value(ctypes.Union):
        _fields_ = [("text", ctypes.c_void_p),
                    ("storage", ctypes.c_byte * (16 if ctypes.sizeof(ctypes.c_void_p) == 8 else 8))]

    class PROPVARIANT(ctypes.Structure):
        _fields_ = [("vt", ctypes.c_ushort), ("reserved", ctypes.c_ushort * 3),
                    ("value", Value)]

    ptr = ctypes.c_void_p
    shell = ctypes.windll.shell32
    ole = ctypes.windll.ole32
    shell.SHGetPropertyStoreForWindow.argtypes = [ptr, ctypes.POINTER(GUID), ctypes.POINTER(ptr)]
    shell.SHGetPropertyStoreForWindow.restype = ctypes.c_long
    ole.CoTaskMemAlloc.argtypes = [ctypes.c_size_t]
    ole.CoTaskMemAlloc.restype = ptr
    ole.PropVariantClear.argtypes = [ctypes.POINTER(PROPVARIANT)]
    iid = GUID.parse("886d8eeb-8cf2-4446-8d02-cdba1dbdcf99")
    fmtid = GUID.parse("9f4c2855-9f79-4b39-a8d0-e1d42de1d5f3")
    store = ptr()
    _check(shell.SHGetPropertyStoreForWindow(hwnd, ctypes.byref(iid), ctypes.byref(store)))
    vtable = ctypes.cast(store, ctypes.POINTER(ctypes.POINTER(ptr))).contents
    release = ctypes.WINFUNCTYPE(ctypes.c_ulong, ptr)(vtable[2])
    set_value = ctypes.WINFUNCTYPE(ctypes.c_long, ptr, ctypes.POINTER(PROPERTYKEY),
                                  ctypes.POINTER(PROPVARIANT))(vtable[6])
    try:
        for prop_id, text in properties:
            key = PROPERTYKEY(fmtid, prop_id)
            value = PROPVARIANT()
            if text is not None:
                buffer = ctypes.create_unicode_buffer(text)
                value.value.text = ole.CoTaskMemAlloc(ctypes.sizeof(buffer))
                if not value.value.text:
                    raise OSError("Could not allocate taskbar property value")
                value.vt = 31  # VT_LPWSTR; PropVariantClear owns the COM-allocated string.
                ctypes.memmove(value.value.text, buffer, ctypes.sizeof(buffer))
            try:
                _check(set_value(store, ctypes.byref(key), ctypes.byref(value)))
            finally:
                ole.PropVariantClear(ctypes.byref(value))
    finally:
        release(store)
