# Setup

1. Install **Godot 4.3+** (4.7 recommended): `winget install GodotEngine.GodotEngine`
2. Open `RevolutionGodot/project.godot` (or: `godot --path RevolutionGodot`).
3. Press **F5** (main scene = `scenes/arena.tscn`).

**Intel HD / older GPUs:** the project uses **GL Compatibility** (not Forward+/Vulkan). If a window still flashes and closes, run:
`godot --path RevolutionGodot --rendering-method gl_compatibility`

## Smoke checks

```
godot --headless --path RevolutionGodot --quit-after 1
godot --headless --path RevolutionGodot --script res://scripts/smoke_test.gd
```

## Controls

| Key | Action |
|---|---|
| A/D | Move |
| Space | Jump |
| LMB / J | Attack |
| Shift | Block / parry |
| S | Dodge |
| Q / E | Lane step |
| T | Grid Stutter |
| R | Rewind |
| 1/2/3 | Weapons |
| Esc | Pause |

## Vertical slice gate

Ash sword-fights one dummy with hitstop/shake; Q/E lanes; T stutter; R rewind; HUD updates.
