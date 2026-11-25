#!/usr/bin/env python3
"""
Gaea-style Fringe terrain export (heightmap + colormap).

Produces the same artifact names Gaea Community would export so the
Blender/Godot pipeline can consume them. Replace these PNGs with real
Gaea exports when QuadSpinner Gaea Community is available.

Outputs (256x256):
  RevolutionGodot/assets/terrain/fringe/heightmap.png   (16-bit grayscale)
  RevolutionGodot/assets/terrain/fringe/colormap.png    (RGB dirt/dust/grass)
"""
from __future__ import annotations

import math
import struct
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "RevolutionGodot" / "assets" / "terrain" / "fringe"
SIZE = 256


def noise2(x: float, y: float) -> float:
    """Cheap value-noise-ish hash."""
    n = math.sin(x * 127.1 + y * 311.7) * 43758.5453
    return n - math.floor(n)


def fbm(x: float, y: float, octaves: int = 5) -> float:
    amp, freq, total, norm = 1.0, 1.0, 0.0, 0.0
    for _ in range(octaves):
        total += amp * noise2(x * freq, y * freq)
        norm += amp
        amp *= 0.5
        freq *= 2.0
    return total / max(norm, 1e-6)


def height_at(u: float, v: float) -> float:
    """
    u,v in [0,1]. X = trail direction, V = depth (far hills at v~0, near at v~1).
    Shallow valley / road bowl along center v≈0.45–0.55 (fight lane).
    """
    hills = fbm(u * 3.2, v * 2.4, 5)
    # Far ridge (low v)
    far = (1.0 - v) ** 1.6 * (0.45 + 0.35 * fbm(u * 2.0, 0.2, 3))
    # Near shoulder (high v)
    near = max(0.0, v - 0.62) ** 1.3 * (0.25 + 0.2 * fbm(u * 4.0 + 10, v * 3.0, 3))
    # Road trench along v≈0.48
    road_d = abs(v - 0.48)
    road = max(0.0, 1.0 - road_d / 0.12) ** 2
    base = 0.22 + 0.18 * hills + far + near
    base -= road * 0.16
    # Gentle lengthwise undulation
    base += 0.03 * math.sin(u * math.pi * 4.0) * (1.0 - road * 0.7)
    return max(0.0, min(1.0, base))


def color_at(u: float, v: float, h: float) -> tuple[int, int, int]:
    road_d = abs(v - 0.48)
    on_road = road_d < 0.10
    # Dust / packed dirt on road, olive scrub on hills, ash-brown mid
    if on_road:
        t = 1.0 - road_d / 0.10
        r = int(110 + 40 * t)
        g = int(85 + 25 * t)
        b = int(55 + 15 * t)
    elif h > 0.55:
        r, g, b = 72, 78, 48  # dry grass ridge
    elif v < 0.35:
        r, g, b = 58, 52, 40  # far slope
    else:
        r, g, b = 90, 70, 48  # shoulder dust
    # Subtle noise grit
    n = noise2(u * 40, v * 40)
    r = max(0, min(255, int(r + (n - 0.5) * 18)))
    g = max(0, min(255, int(g + (n - 0.5) * 14)))
    b = max(0, min(255, int(b + (n - 0.5) * 10)))
    return r, g, b


def write_png_gray16(path: Path, pixels: list[int], w: int, h: int) -> None:
    """Minimal 16-bit grayscale PNG writer."""
    raw = bytearray()
    for y in range(h):
        raw.append(0)  # filter None
        for x in range(w):
            val = pixels[y * w + x] & 0xFFFF
            raw.append((val >> 8) & 0xFF)
            raw.append(val & 0xFF)

    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", w, h, 16, 0, 0, 0, 0)
    png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(bytes(raw), 9)) + chunk(b"IEND", b"")
    path.write_bytes(png)


def write_png_rgb8(path: Path, pixels: list[tuple[int, int, int]], w: int, h: int) -> None:
    raw = bytearray()
    for y in range(h):
        raw.append(0)
        for x in range(w):
            r, g, b = pixels[y * w + x]
            raw.extend((r, g, b))

    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)
    png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(bytes(raw), 9)) + chunk(b"IEND", b"")
    path.write_bytes(png)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    heights: list[int] = []
    colors: list[tuple[int, int, int]] = []
    for y in range(SIZE):
        v = y / (SIZE - 1)
        for x in range(SIZE):
            u = x / (SIZE - 1)
            h = height_at(u, v)
            heights.append(int(h * 65535))
            colors.append(color_at(u, v, h))

    hm = OUT / "heightmap.png"
    cm = OUT / "colormap.png"
    write_png_gray16(hm, heights, SIZE, SIZE)
    write_png_rgb8(cm, colors, SIZE, SIZE)
    print(f"Wrote {hm}")
    print(f"Wrote {cm}")
    print("Gaea Community: recreate this tile and overwrite these PNGs when available.")


if __name__ == "__main__":
    main()
