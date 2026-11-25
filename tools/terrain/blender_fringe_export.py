"""
Blender script: heightmap + colormap → fringe_terrain.glb (+ simple props).

Run:
  blender --background --python tools/terrain/blender_fringe_export.py

Expects:
  RevolutionGodot/assets/terrain/fringe/heightmap.png
  RevolutionGodot/assets/terrain/fringe/colormap.png
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import bpy

# When run via blender --python, __file__ may be missing on some builds.
ROOT = Path(r"c:\Users\itsma\OneDrive\Desktop\revolution")
FRINGE = ROOT / "RevolutionGodot" / "assets" / "terrain" / "fringe"
HEIGHTMAP = FRINGE / "heightmap.png"
COLORMAP = FRINGE / "colormap.png"
OUT_TERRAIN = FRINGE / "fringe_terrain.glb"
OUT_PROPS = FRINGE / "fringe_props.glb"

# World size matching arena (~60 x 12)
SIZE_X = 60.0
SIZE_Z = 14.0
HEIGHT_Y = 4.5
RES = 128  # mesh resolution (Intel HD friendly)


def clear_scene() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for block in bpy.data.meshes:
        if block.users == 0:
            bpy.data.meshes.remove(block)
    for block in bpy.data.materials:
        if block.users == 0:
            bpy.data.materials.remove(block)


def load_height_pixels():
    img = bpy.data.images.load(str(HEIGHTMAP))
    img.colorspace_settings.name = "Non-Color"
    w, h = img.size[0], img.size[1]
    pixels = list(img.pixels)  # RGBA float
    return img, w, h, pixels


def sample_h(pixels, w, h, u, v) -> float:
    x = min(w - 1, max(0, int(u * (w - 1))))
    y = min(h - 1, max(0, int(v * (h - 1))))
    i = (y * w + x) * 4
    return pixels[i]  # R channel


def build_terrain() -> bpy.types.Object:
    _, w, h, pixels = load_height_pixels()
    verts = []
    faces = []
    uvs = []
    for iz in range(RES):
        v = iz / (RES - 1)
        z = (v - 0.5) * SIZE_Z
        for ix in range(RES):
            u = ix / (RES - 1)
            x = (u - 0.5) * SIZE_X
            hv = sample_h(pixels, w, h, u, 1.0 - v)
            y = hv * HEIGHT_Y
            verts.append((x, y, z))
            uvs.append((u, v))
    for iz in range(RES - 1):
        for ix in range(RES - 1):
            i0 = iz * RES + ix
            i1 = i0 + 1
            i2 = i0 + RES
            i3 = i2 + 1
            faces.append((i0, i1, i3, i2))

    mesh = bpy.data.meshes.new("FringeTerrain")
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    # UVs
    mesh.uv_layers.new(name="UVMap")
    uv_layer = mesh.uv_layers.active.data
    # after from_pydata, loops exist
    # Build loop UVs from face corners
    # Simpler: assign per-loop from vertex index
    vert_uv = {i: uvs[i] for i in range(len(uvs))}
    for poly in mesh.polygons:
        for li in poly.loop_indices:
            vi = mesh.loops[li].vertex_index
            uv_layer[li].uv = vert_uv[vi]

    obj = bpy.data.objects.new("FringeTerrain", mesh)
    bpy.context.collection.objects.link(obj)

    # Material with colormap
    mat = bpy.data.materials.new("FringeDirt")
    mat.use_nodes = True
    nt = mat.node_tree
    nodes = nt.nodes
    links = nt.links
    nodes.clear()
    out = nodes.new("ShaderNodeOutputMaterial")
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    tex = nodes.new("ShaderNodeTexImage")
    if COLORMAP.is_file():
        tex.image = bpy.data.images.load(str(COLORMAP))
    links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    bsdf.inputs["Roughness"].default_value = 0.92
    obj.data.materials.append(mat)
    return obj


def add_prop_cube(name, loc, scale, color):
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=loc)
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = scale
    mat = bpy.data.materials.new(name + "Mat")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (*color, 1.0)
        bsdf.inputs["Roughness"].default_value = 0.9
    obj.data.materials.append(mat)
    return obj


def add_prop_cylinder(name, loc, radius, depth, color):
    bpy.ops.mesh.primitive_cylinder_add(radius=radius, depth=depth, location=loc)
    obj = bpy.context.active_object
    obj.name = name
    mat = bpy.data.materials.new(name + "Mat")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (*color, 1.0)
    obj.data.materials.append(mat)
    return obj


def build_props() -> list:
    props = []
    # Fence posts + rails sample
    for i in range(8):
        x = -12.0 + i * 3.5
        props.append(add_prop_cylinder(f"FencePost_{i}", (x, 0.55, -2.6), 0.06, 1.1, (0.28, 0.2, 0.12)))
        if i < 7:
            props.append(add_prop_cube(f"FenceRail_{i}", (x + 1.75, 0.7, -2.6), (1.6, 0.06, 0.06), (0.32, 0.22, 0.14)))
    # Trees (trunk + canopy)
    for i, x in enumerate([-10, -4, 2, 8, 14, 20]):
        props.append(add_prop_cylinder(f"Trunk_{i}", (x, 1.2, -5.5 - (i % 3) * 0.4), 0.18, 2.4, (0.25, 0.16, 0.1)))
        bpy.ops.mesh.primitive_uv_sphere_add(radius=1.1, location=(x, 2.8, -5.5 - (i % 3) * 0.4))
        canopy = bpy.context.active_object
        canopy.name = f"Canopy_{i}"
        mat = bpy.data.materials.new(f"CanopyMat_{i}")
        mat.use_nodes = True
        bsdf = mat.node_tree.nodes.get("Principled BSDF")
        if bsdf:
            bsdf.inputs["Base Color"].default_value = (0.22, 0.28, 0.14, 1.0)
        canopy.data.materials.append(mat)
        props.append(canopy)
    # Barn husk
    props.append(add_prop_cube("Barn", (16.0, 2.0, -3.2), (3.2, 4.0, 2.4), (0.35, 0.22, 0.16)))
    props.append(add_prop_cube("BarnWindow", (16.0, 2.2, -2.0), (0.8, 0.9, 0.1), (0.05, 0.04, 0.03)))
    # Crates / barrels
    props.append(add_prop_cube("CrateA", (-3.0, 0.4, 2.0), (0.8, 0.8, 0.7), (0.4, 0.3, 0.2)))
    props.append(add_prop_cylinder("BarrelA", (7.5, 0.45, 1.9), 0.35, 0.9, (0.3, 0.2, 0.12)))
    return props


def export_glb(path: Path, objects: list) -> None:
    bpy.ops.object.select_all(action="DESELECT")
    for obj in objects:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = objects[0]
    path.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.export_scene.gltf(
        filepath=str(path),
        export_format="GLB",
        use_selection=True,
        export_apply=True,
    )


def main() -> None:
    if not HEIGHTMAP.is_file():
        print("Missing heightmap:", HEIGHTMAP, file=sys.stderr)
        sys.exit(1)
    clear_scene()
    terrain = build_terrain()
    export_glb(OUT_TERRAIN, [terrain])
    print("Wrote", OUT_TERRAIN)

    clear_scene()
    props = build_props()
    export_glb(OUT_PROPS, props)
    print("Wrote", OUT_PROPS)


if __name__ == "__main__":
    main()
