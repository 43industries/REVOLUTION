#!/usr/bin/env python3
"""
Fallback (no Blender): convert fringe heightmap+colormap to a minimal glTF 2.0 .glb
suitable for Godot import. Also writes a simple props glb via the same writer.
"""
from __future__ import annotations

import json
import math
import struct
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FRINGE = ROOT / "RevolutionGodot" / "assets" / "terrain" / "fringe"
HEIGHTMAP = FRINGE / "heightmap.png"
COLORMAP = FRINGE / "colormap.png"
OUT_TERRAIN = FRINGE / "fringe_terrain.glb"
OUT_PROPS = FRINGE / "fringe_props.glb"

SIZE_X = 60.0
SIZE_Z = 14.0
HEIGHT_Y = 4.5
RES = 96


def read_png(path: Path):
    data = path.read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    pos = 8
    width = height = None
    bit_depth = color_type = None
    idat = b""
    while pos < len(data):
        length = struct.unpack(">I", data[pos : pos + 4])[0]
        tag = data[pos + 4 : pos + 8]
        chunk = data[pos + 8 : pos + 8 + length]
        pos += 12 + length
        if tag == b"IHDR":
            width, height, bit_depth, color_type = struct.unpack(">IIBB", chunk[:10])
        elif tag == b"IDAT":
            idat += chunk
        elif tag == b"IEND":
            break
    raw = zlib.decompress(idat)
    rows = []
    stride = width * (2 if (bit_depth == 16 and color_type == 0) else (3 if color_type == 2 else 1))
    if bit_depth == 16 and color_type == 0:
        stride = width * 2
    elif color_type == 2 and bit_depth == 8:
        stride = width * 3
    elif color_type == 6 and bit_depth == 8:
        stride = width * 4
    else:
        stride = width * max(1, bit_depth // 8)
    i = 0
    for y in range(height):
        i += 1  # filter
        row = raw[i : i + stride]
        i += stride
        rows.append(row)
    return width, height, bit_depth, color_type, rows


def sample_height(rows, w, h, u, v) -> float:
    x = min(w - 1, max(0, int(u * (w - 1))))
    y = min(h - 1, max(0, int((1.0 - v) * (h - 1))))
    row = rows[y]
    # 16-bit gray big-endian
    o = x * 2
    val = (row[o] << 8) | row[o + 1]
    return val / 65535.0


def sample_color(rows, w, h, u, v, color_type) -> tuple[float, float, float]:
    x = min(w - 1, max(0, int(u * (w - 1))))
    y = min(h - 1, max(0, int((1.0 - v) * (h - 1))))
    row = rows[y]
    if color_type == 2:
        o = x * 3
        return row[o] / 255.0, row[o + 1] / 255.0, row[o + 2] / 255.0
    if color_type == 6:
        o = x * 4
        return row[o] / 255.0, row[o + 1] / 255.0, row[o + 2] / 255.0
    return 0.4, 0.3, 0.2


def build_terrain_mesh():
    hw, hh, bd, ct, hrows = read_png(HEIGHTMAP)
    cw, ch, cbd, cct, crows = read_png(COLORMAP)
    positions = []
    normals = []
    uvs = []
    colors = []
    indices = []
    for iz in range(RES):
        v = iz / (RES - 1)
        z = (v - 0.5) * SIZE_Z
        for ix in range(RES):
            u = ix / (RES - 1)
            x = (u - 0.5) * SIZE_X
            hv = sample_height(hrows, hw, hh, u, v)
            y = hv * HEIGHT_Y
            positions.extend((x, y, z))
            uvs.extend((u, v))
            r, g, b = sample_color(crows, cw, ch, u, v, cct)
            colors.extend((r, g, b, 1.0))
            normals.extend((0.0, 1.0, 0.0))
    for iz in range(RES - 1):
        for ix in range(RES - 1):
            i0 = iz * RES + ix
            i1 = i0 + 1
            i2 = i0 + RES
            i3 = i2 + 1
            indices.extend((i0, i2, i1, i1, i2, i3))
    # Recompute normals
    normals = [0.0] * (RES * RES * 3)
    for t in range(0, len(indices), 3):
        a, b, c = indices[t], indices[t + 1], indices[t + 2]
        ax, ay, az = positions[a * 3 : a * 3 + 3]
        bx, by, bz = positions[b * 3 : b * 3 + 3]
        cx, cy, cz = positions[c * 3 : c * 3 + 3]
        ux, uy, uz = bx - ax, by - ay, bz - az
        vx, vy, vz = cx - ax, cy - ay, cz - az
        nx, ny, nz = uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx
        for i in (a, b, c):
            normals[i * 3] += nx
            normals[i * 3 + 1] += ny
            normals[i * 3 + 2] += nz
    for i in range(RES * RES):
        nx, ny, nz = normals[i * 3 : i * 3 + 3]
        L = math.sqrt(nx * nx + ny * ny + nz * nz) or 1.0
        normals[i * 3 : i * 3 + 3] = [nx / L, ny / L, nz / L]
    return positions, normals, uvs, colors, indices


def pack_f32(vals):
    return b"".join(struct.pack("<f", float(v)) for v in vals)


def pack_u16(vals):
    return b"".join(struct.pack("<H", int(v)) for v in vals)


def write_glb(path: Path, positions, normals, uvs, colors, indices, name="Mesh"):
    # pad to 4 bytes
    def pad4(b: bytes) -> bytes:
        return b + b"\x00" * ((4 - (len(b) % 4)) % 4)

    bin_blob = b""
    accessors = []
    buffer_views = []

    def add_f32(data, typ, count, mins=None, maxs=None):
        nonlocal bin_blob
        offset = len(bin_blob)
        raw = pack_f32(data)
        bin_blob += pad4(raw)
        buffer_views.append({"buffer": 0, "byteOffset": offset, "byteLength": len(raw), "target": 34962})
        acc = {"bufferView": len(buffer_views) - 1, "componentType": 5126, "count": count, "type": typ}
        if mins is not None:
            acc["min"] = mins
            acc["max"] = maxs
        accessors.append(acc)
        return len(accessors) - 1

    def add_u16(data):
        nonlocal bin_blob
        offset = len(bin_blob)
        raw = pack_u16(data)
        bin_blob += pad4(raw)
        buffer_views.append({"buffer": 0, "byteOffset": offset, "byteLength": len(raw), "target": 34963})
        accessors.append({"bufferView": len(buffer_views) - 1, "componentType": 5123, "count": len(data), "type": "SCALAR"})
        return len(accessors) - 1

    nvert = len(positions) // 3
    xs = positions[0::3]
    ys = positions[1::3]
    zs = positions[2::3]
    pi = add_f32(positions, "VEC3", nvert, [min(xs), min(ys), min(zs)], [max(xs), max(ys), max(zs)])
    ni = add_f32(normals, "VEC3", nvert)
    ui = add_f32(uvs, "VEC2", nvert)
    ci = add_f32(colors, "VEC4", nvert)
    ii = add_u16(indices)

    gltf = {
        "asset": {"version": "2.0", "generator": "heightmap_to_glb"},
        "buffers": [{"byteLength": len(bin_blob)}],
        "bufferViews": buffer_views,
        "accessors": accessors,
        "materials": [{
            "name": "FringeDirt",
            "pbrMetallicRoughness": {
                "baseColorFactor": [1, 1, 1, 1],
                "metallicFactor": 0.0,
                "roughnessFactor": 0.92,
            },
        }],
        "meshes": [{
            "name": name,
            "primitives": [{
                "attributes": {"POSITION": pi, "NORMAL": ni, "TEXCOORD_0": ui, "COLOR_0": ci},
                "indices": ii,
                "material": 0,
            }],
        }],
        "nodes": [{"name": name, "mesh": 0}],
        "scenes": [{"nodes": [0]}],
        "scene": 0,
    }
    json_bytes = pad4(json.dumps(gltf, separators=(",", ":")).encode("utf-8"))
    bin_padded = pad4(bin_blob)
    total = 12 + 8 + len(json_bytes) + 8 + len(bin_padded)
    out = b""
    out += struct.pack("<III", 0x46546C67, 2, total)
    out += struct.pack("<II", len(json_bytes), 0x4E4F534A)
    out += json_bytes
    out += struct.pack("<II", len(bin_padded), 0x004E4942)
    out += bin_padded
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(out)
    print(f"Wrote {path} ({len(out)} bytes)")


def build_simple_props():
    """A few boxes/cylinders as one combined mesh for props glb."""
    positions = []
    normals = []
    uvs = []
    colors = []
    indices = []

    def add_box(cx, cy, cz, sx, sy, sz, col):
        base = len(positions) // 3
        # 8 verts
        for dx in (-0.5, 0.5):
            for dy in (-0.5, 0.5):
                for dz in (-0.5, 0.5):
                    positions.extend((cx + dx * sx, cy + dy * sy, cz + dz * sz))
                    normals.extend((0, 1, 0))
                    uvs.extend((0, 0))
                    colors.extend((*col, 1.0))
        # rough faces using corner indices — not perfect normals but fine for silhouettes
        faces = [
            (0, 1, 3, 2), (4, 6, 7, 5), (0, 2, 6, 4),
            (1, 5, 7, 3), (0, 4, 5, 1), (2, 3, 7, 6),
        ]
        # remap: our loop order is dx,dy,dz nested wrong. Use unit cube verts properly.
        # Rebuild last 8 verts correctly
        pass

    # Simpler: emit triangle pairs for axis-aligned boxes via explicit verts
    def box(cx, cy, cz, sx, sy, sz, col):
        hx, hy, hz = sx * 0.5, sy * 0.5, sz * 0.5
        corners = [
            (cx - hx, cy - hy, cz - hz),
            (cx + hx, cy - hy, cz - hz),
            (cx + hx, cy + hy, cz - hz),
            (cx - hx, cy + hy, cz - hz),
            (cx - hx, cy - hy, cz + hz),
            (cx + hx, cy - hy, cz + hz),
            (cx + hx, cy + hy, cz + hz),
            (cx - hx, cy + hy, cz + hz),
        ]
        faces = [
            (0, 1, 2, 3), (5, 4, 7, 6), (4, 0, 3, 7),
            (1, 5, 6, 2), (3, 2, 6, 7), (4, 5, 1, 0),
        ]
        for face in faces:
            b = len(positions) // 3
            for vi in face:
                positions.extend(corners[vi])
                normals.extend((0, 1, 0))
                uvs.extend((0, 0))
                colors.extend((*col, 1.0))
            indices.extend((b, b + 1, b + 2, b, b + 2, b + 3))

    wood = (0.35, 0.22, 0.14)
    bark = (0.25, 0.16, 0.1)
    leaf = (0.2, 0.28, 0.12)
    for i in range(8):
        x = -12.0 + i * 3.5
        box(x, 0.55, -2.6, 0.12, 1.1, 0.12, wood)
        if i < 7:
            box(x + 1.75, 0.7, -2.6, 3.2, 0.08, 0.08, wood)
    for i, x in enumerate([-10, -4, 2, 8, 14, 20]):
        z = -5.5 - (i % 3) * 0.4
        box(x, 1.2, z, 0.35, 2.4, 0.35, bark)
        box(x, 2.7, z, 2.0, 1.6, 2.0, leaf)
    box(16.0, 2.0, -3.2, 3.2, 4.0, 2.4, (0.35, 0.22, 0.16))
    box(-3.0, 0.4, 2.0, 0.8, 0.8, 0.7, wood)
    box(7.5, 0.45, 1.9, 0.7, 0.9, 0.7, (0.3, 0.2, 0.12))
    return positions, normals, uvs, colors, indices


def main():
    if not HEIGHTMAP.is_file():
        raise SystemExit(f"Missing {HEIGHTMAP} — run generate_fringe_gaea_style.py first")
    pos, nrm, uv, col, idx = build_terrain_mesh()
    write_glb(OUT_TERRAIN, pos, nrm, uv, col, idx, "FringeTerrain")
    pos, nrm, uv, col, idx = build_simple_props()
    write_glb(OUT_PROPS, pos, nrm, uv, col, idx, "FringeProps")


if __name__ == "__main__":
    main()
