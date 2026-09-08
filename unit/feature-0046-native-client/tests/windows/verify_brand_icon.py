"""Verify shipped PE icon bytes and live native window/tray icons without AI calls.

Run with Windows build Python (pefile comes with PyInstaller):
  verify_brand_icon.py --src <src> --app <app.exe> --setup <setup.exe> --out <dir>
"""
from __future__ import annotations

import argparse
import ctypes
import json
import struct
import threading
import time
from ctypes import wintypes
from pathlib import Path
import sys

import pefile


def ico_frames(path):
    data = path.read_bytes()
    reserved, kind, count = struct.unpack_from('<HHH', data)
    assert (reserved, kind) == (0, 1)
    frames = []
    for i in range(count):
        w, h, _, _, _, _, size, offset = struct.unpack_from('<BBBBHHII', data, 6 + i * 16)
        frames.append((w or 256, h or 256, data[offset:offset + size]))
    return frames


def pe_icons(path, frames):
    with pefile.PE(str(path)) as pe:
        payloads = []
        for entry in pe.DIRECTORY_ENTRY_RESOURCE.entries:
            if entry.id == 3:  # RT_ICON
                for icon in entry.directory.entries:
                    for lang in icon.directory.entries:
                        d = lang.data.struct
                        payloads.append(pe.get_data(d.OffsetToData, d.Size))
        matched = [w for w, h, payload in frames if payload in payloads]
        assert len(matched) == len(frames), (str(path), matched)
        return {'file': path.name, 'matched_sizes': matched}


def main():
    ap = argparse.ArgumentParser()
    for name in ('src', 'app', 'setup', 'out'):
        ap.add_argument('--' + name, type=Path, required=True)
    ap.add_argument('--surface', choices=('native', 'webview'), default='native')
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(args.src))
    from client import branding, tray, window

    result = {'pe': [], 'native': {}, 'surface': args.surface, 'verdict': 'RUNNING'}
    (args.out / 'result.json').write_text(json.dumps(result), encoding='utf-8')
    try:
        frames = ico_frames(branding.ICON_PATH)
        assert {w for w, _, _ in frames} == {16, 20, 24, 32, 40, 48, 64, 128, 256}
        result['pe'] = [pe_icons(p, frames) for p in (args.app, args.setup)]
        bundled = args.app.parent / '_internal/client/assets/dqa.ico'
        assert bundled.read_bytes() == branding.ICON_PATH.read_bytes()
        result['bundle_bytes_equal'] = True

        import clr
        clr.AddReference('System.Drawing')
        from System import Array, Byte, Int64, IntPtr
        from System.Drawing import Bitmap, Icon
        from System.IO import MemoryStream
        from System.Drawing.Imaging import ImageFormat

        result['alpha'] = []
        for width, height, payload in frames:
            single = (struct.pack('<HHH', 0, 1, 1)
                      + struct.pack('<BBBBHHII', width % 256, height % 256,
                                    0, 0, 1, 32, len(payload), 22) + payload)
            png_frame = payload.startswith(b'\x89PNG')
            stream = MemoryStream(Array[Byte](payload if png_frame else single))
            frame_icon = None if png_frame else Icon(stream)
            bitmap = Bitmap(stream) if png_frame else frame_icon.ToBitmap()
            alphas = [bitmap.GetPixel(x, y).A for y in range(height) for x in range(width)]
            corners = [bitmap.GetPixel(x, y).A for x, y in
                       ((0, 0), (width - 1, 0), (0, height - 1), (width - 1, height - 1))]
            assert min(alphas) == 0 and max(alphas) == 255 and corners == [0] * 4
            result['alpha'].append({'size': width, 'min': min(alphas), 'max': max(alphas),
                                    'corners': corners})
            bitmap.Dispose()
            if frame_icon is not None:
                frame_icon.Dispose()
            stream.Dispose()

        def compare_icon(icon, label):
            actual = icon.ToBitmap()
            payload = next(data for w, h, data in frames
                           if (w, h) == (actual.Width, actual.Height))
            single_frame = (struct.pack('<HHH', 0, 1, 1)
                            + struct.pack('<BBBBHHII', actual.Width % 256,
                                          actual.Height % 256, 0, 0, 1, 32, len(payload), 22)
                            + payload)
            stream = MemoryStream(Array[Byte](single_frame))
            expected_icon = Icon(stream)
            expected = expected_icon.ToBitmap()
            equal = all(actual.GetPixel(x, y).ToArgb() == expected.GetPixel(x, y).ToArgb()
                        for y in range(actual.Height) for x in range(actual.Width))
            actual.Save(str(args.out / (label + '.png')), ImageFormat.Png)
            result['native'][label] = {'pixels_equal': equal, 'width': actual.Width,
                                      'height': actual.Height}
            expected.Dispose()
            expected_icon.Dispose()
            stream.Dispose()
            actual.Dispose()
            assert equal, label

        user32 = ctypes.windll.user32
        shell32 = ctypes.windll.shell32
        shell32.ExtractIconW.argtypes = [wintypes.HINSTANCE, wintypes.LPCWSTR, wintypes.UINT]
        shell32.ExtractIconW.restype = wintypes.HICON
        user32.DestroyIcon.argtypes = [wintypes.HICON]
        for path, label in ((args.app, 'app-exe'), (args.setup, 'setup-exe')):
            hicon = shell32.ExtractIconW(None, str(path), 0)
            assert int(hicon or 0) not in (0, 1), label
            try:
                compare_icon(Icon.FromHandle(IntPtr(Int64(ctypes.c_ssize_t(hicon).value))), label)
            finally:
                user32.DestroyIcon(hicon)
        user32.GetClassLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int]
        user32.GetClassLongPtrW.restype = ctypes.c_void_p
        user32.SendMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
        user32.SendMessageW.restype = ctypes.c_void_p
        if args.surface == 'native':
            branding.initialize_process()
            t = tray.Tray(title='DQA icon verification')
            try:
                assert t.start(), t.last_error
                hicon = user32.GetClassLongPtrW(t.backend.hwnd, -14)
                assert hicon
                icon = Icon.FromHandle(IntPtr(Int64(ctypes.c_ssize_t(hicon).value)))
                compare_icon(icon, 'tray')
            finally:
                t.stop()

            import tkinter as tk
            root = tk.Tk()
            try:
                root.title('DQA icon verification')
                branding.bind_tk_window(root)
                root.update()
                user32.GetParent.argtypes = [wintypes.HWND]
                user32.GetParent.restype = wintypes.HWND
                hwnd = int(root.frame(), 0)
                hicon = (user32.SendMessageW(hwnd, 0x007F, 1, 0)  # WM_GETICON / ICON_BIG
                         or user32.GetClassLongPtrW(hwnd, -14))
                assert hicon, (hwnd, root.winfo_id(), root.iconbitmap())
                compare_icon(Icon.FromHandle(IntPtr(Int64(ctypes.c_ssize_t(hicon).value))), 'tk-window')
            finally:
                branding.clear_window(int(root.frame(), 0))
                root.destroy()

        if args.surface == 'webview':
            sh = window.Shell('about:blank', 'DQA icon verification', str(args.out / 'webview-profile'))
            failures = []

            def inspect_window():
                try:
                    deadline = time.monotonic() + 45
                    while sh._window is None and time.monotonic() < deadline:
                        time.sleep(0.05)
                    assert sh._window is not None, 'WebView2 creation timeout'
                    assert sh._window.events.shown.wait(45), 'WebView2 show timeout'
                    from webview.platforms.winforms import BrowserView
                    compare_icon(BrowserView.instances[sh._window.uid].Icon, 'webview-window')
                except Exception as exc:
                    failures.append(repr(exc))
                finally:
                    sh.quit()

            worker = threading.Thread(target=inspect_window, daemon=True)
            worker.start()
            assert sh.run(), sh.last_error
            worker.join(timeout=50)
            assert not worker.is_alive() and not failures, failures
        assert len(result['native']) == (4 if args.surface == 'native' else 3)
        result['verdict'] = 'PASS'
    except Exception as exc:
        result['verdict'] = 'FAIL'
        result['error'] = repr(exc)
        raise
    finally:
        (args.out / 'result.json').write_text(json.dumps(result, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
