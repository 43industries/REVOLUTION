# RevolutionGodot — Anime 3D Remake

Godot 4 remake of REVOLUTION. Replaces the former Unreal `RevolutionUE` scaffold.

**Presentation:** 3D side-scroller with toon shading  
**Combat axes:** X/Z + **W** lanes + **T** stutter/rewind  
**Reference build:** `../revolution.py` (pygame) still playable via `../Play.bat`

## Quick start

```bash
winget install GodotEngine.GodotEngine
godot --path .
```

Or open this folder in the Godot editor and press F5.

## Layout

| Path | Role |
|---|---|
| `scenes/arena.tscn` | Main slice: arena, Ash, dummy, camera, HUD |
| `scripts/combat.gd` | Sword phases, damage, hurt flash |
| `scripts/w_lane.gd` | 5-lane depth |
| `scripts/time_rewind.gd` | Stutter + rewind buffer |
| `shaders/toon.gdshader` | Cel shading |
| `data/WeaponProfiles.json` | Ported from pygame / former UE data |
| `docs/Anime3DPipeline.md` | VRoid swap path |

## Docs

- [SETUP.md](docs/SETUP.md)
- [Anime3DPipeline.md](docs/Anime3DPipeline.md)
