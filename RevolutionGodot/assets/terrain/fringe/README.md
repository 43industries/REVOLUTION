# Fringe terrain (Gaea → Blender → Godot)

## Current artifacts
| File | Role |
|---|---|
| `heightmap.png` | 16-bit grayscale bowl/road (Gaea-style generator) |
| `colormap.png` | Dirt / dust / dry-grass colors |
| `fringe_terrain.glb` | Playable terrain mesh |
| `fringe_props.glb` | Fence / trees / barn / crates |

## Regenerate with tools in repo
```bat
python tools\terrain\generate_fringe_gaea_style.py
python tools\terrain\heightmap_to_glb.py
```

## Real Gaea Community
1. Build a 256–512 tile: valley road along X, hills on far Z.
2. Export 16-bit height + RGB color → overwrite `heightmap.png` / `colormap.png`.
3. Re-run `heightmap_to_glb.py` **or** Blender:

```bat
blender --background --python tools\terrain\blender_fringe_export.py
```

## Godot
`arena.tscn` instances the glbs when present; `env_set.gd` adds chalk/banners and procedural fallback hills if glbs are missing.
