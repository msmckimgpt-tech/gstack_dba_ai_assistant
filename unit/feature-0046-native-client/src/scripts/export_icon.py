"""Render the transparent SVG master to PNG/ICO (CairoSVG/Pillow are build-time only)."""
from __future__ import annotations

import io
import shutil
import struct
from pathlib import Path

from PIL import Image

ASSETS = Path(__file__).resolve().parents[1] / 'client' / 'assets'
SIZES = (16, 20, 24, 32, 40, 48, 64, 128, 256)


def export_icon(source: Path, destination: Path) -> None:
    frames = []
    with Image.open(source) as original:
        image = original.convert('RGBA')
        for size in SIZES:
            buffer = io.BytesIO()
            # Tk 8.6 scales the first PNG entry; DIB frames preserve the intended size.
            options = {'bitmap_format': 'bmp'} if size < 256 else {}
            image.save(buffer, format='ICO', sizes=[(size, size)], **options)
            data = buffer.getvalue()
            entry = bytearray(data[6:22])
            length, offset = struct.unpack_from('<II', entry, 8)
            frames.append((entry, data[offset:offset + length]))

    offset = 6 + 16 * len(frames)
    entries, payloads = [], []
    for entry, payload in frames:
        struct.pack_into('<I', entry, 12, offset)
        entries.append(entry)
        payloads.append(payload)
        offset += len(payload)
    destination.write_bytes(struct.pack('<HHH', 0, 1, len(frames))
                            + b''.join(entries) + b''.join(payloads))


if __name__ == '__main__':
    import cairosvg

    cairosvg.svg2png(url=str(ASSETS / 'dqa.svg'), write_to=str(ASSETS / 'dqa.png'),
                    output_width=1024, output_height=1024)
    export_icon(ASSETS / 'dqa.png', ASSETS / 'dqa.ico')
    web = ASSETS.parents[4] / 'unit/feature-0003-agent-web-ui/src/static/brand'
    web.mkdir(parents=True, exist_ok=True)
    for name in ('dqa.svg', 'dqa.ico'):
        shutil.copy2(ASSETS / name, web / name)
