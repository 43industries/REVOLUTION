# Anime 3D Pipeline (Godot 4)

REVOLUTION is a **3D side-scroller** with **4D combat axes**: world X/Y/Z meshes, **W** depth lanes, **T** stutter/rewind. Art target is **anime stylized 3D** (VRoid / glTF + cel/toon).

Placeholders first: capsule humanoids in `placeholder_body.gd`. Anime characters drop in later **without rewriting combat**.

## Locked socket names

| Constant | Node name | Purpose |
|---|---|---|
| `SOCKET_WEAPON_R` | `weapon_r` | Sword / bow / crossbow |
| `SOCKET_WEAPON_L` | `weapon_l` | Off-hand |
| `SOCKET_SPINE` | `spine_03` | Hurt / chronal attach |
| `SOCKET_HEAD` | `head` | Head mesh / look |

## Animation slots (future AnimationTree)

| Slot | Used for |
|---|---|
| `full_body` | Dodge, slam, death |
| `upper_body` | Sword / bow / xbow |

## Shader contract (`shaders/toon.gdshader`)

| Uniform | Source |
|---|---|
| `hurt_flash` | `Combat.hurt_flash` via `ToonDriver` |
| `chronal_rim` | `TimeRewind` stutter / afterimage |
| `lane_tint` | `WLane.lane_tint()` |
| `specular_step` | Artist |
| `rim_color` | Artist (default cyan) |
| `outline_width` | `outline.gdshader` next_pass |

## VRoid / glTF import checklist

1. Export UE-compatible or Godot-ready glTF from VRoid.
2. Import to `res://characters/ash_anime/`.
3. Retarget with **SkeletonProfileHumanoid** / BoneMap to keep montage intent.
4. Parent mesh under `Ash/Visuals`; keep sockets above as `BoneAttachment3D` or `Marker3D`.
5. Assign `toon.gdshader` ShaderMaterial (+ outline next_pass).
6. Verify: walk, jump, sword hit dummy, Q/E ghosts, T rim, R rewind.
7. Do **not** change `combat.gd` hit logic for the swap.

## Arena lighting

Strong directional key for cel bands; soft fill; ember ambient. Avoid photoreal skin response.
