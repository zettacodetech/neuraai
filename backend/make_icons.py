"""PWA ikonkalarini hosil qiladi (PNG, faqat stdlib).

Ishlatish: ./venv/bin/python make_icons.py
"""

import math
import os
import struct
import zlib

OUT = os.path.join(os.path.dirname(__file__), "..", "frontend", "icons")
ACCENT = (124, 108, 255)
ACCENT2 = (79, 172, 254)


def _chunk(tag: bytes, data: bytes) -> bytes:
    return (
        struct.pack(">I", len(data))
        + tag
        + data
        + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    )


def _png(size: int, pixels: list[bytes]) -> bytes:
    raw = b"".join(b"\x00" + row for row in pixels)
    return (
        b"\x89PNG\r\n\x1a\n"
        + _chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0))
        + _chunk(b"IDAT", zlib.compress(raw, 9))
        + _chunk(b"IEND", b"")
    )


def _in_round_rect(x: float, y: float, size: float, r: float) -> bool:
    x, y = max(0, min(size - 1, x)), max(0, min(size - 1, y))
    cx = min(max(x, r), size - 1 - r)
    cy = min(max(y, r), size - 1 - r)
    return (x - cx) ** 2 + (y - cy) ** 2 <= r * r


def _sparkle(x: float, y: float, cx: float, cy: float, size: float) -> bool:
    dx, dy = x - cx, y - cy
    r1 = size * 0.30
    r2 = size * 0.14
    return abs(dx) + abs(dy) <= r1 or (abs(dx) <= r2 and abs(dy) <= r2)


def make_icon(size: int) -> bytes:
    r = size * 0.22
    cx = cy = size / 2
    rows = []
    for y in range(size):
        row = bytearray()
        for x in range(size):
            if not _in_round_rect(x, y, size, r):
                row += b"\x00\x00\x00\x00"
                continue
            t = (x + y) / (2 * size)
            base = (
                int(ACCENT[0] + (ACCENT2[0] - ACCENT[0]) * t),
                int(ACCENT[1] + (ACCENT2[1] - ACCENT[1]) * t),
                int(ACCENT[2] + (ACCENT2[2] - ACCENT[2]) * t),
            )
            if _sparkle(x, y, cx, cy, size):
                edge = min(
                    abs(abs(x - cx) + abs(y - cy) - size * 0.30),
                    abs(max(abs(x - cx), abs(y - cy)) - size * 0.14),
                )
                a = 255 if edge > 2 else 160
                row += bytes((255, 255, 255, a))
            else:
                row += bytes(base + (255,))
        rows.append(bytes(row))
    return _png(size, rows)


def main() -> None:
    os.makedirs(OUT, exist_ok=True)
    for s in (192, 512):
        path = os.path.join(OUT, f"icon-{s}.png")
        with open(path, "wb") as f:
            f.write(make_icon(s))
        print(f"Yaratildi: {path} ({s}x{s})")


if __name__ == "__main__":
    main()
