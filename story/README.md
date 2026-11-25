# Shared campaign story

`campaign_story.json` is the source of truth for Ash Trace / Mira / Monroe narrative.

| Consumer | Path |
|---|---|
| Pygame | loads `story/campaign_story.json` (see `revolution.py`) |
| Godot | `RevolutionGodot/data/campaign_story.json` (copy; keep in sync) |

Edit the root `story/campaign_story.json`, then copy into Godot data:

```
copy story\campaign_story.json RevolutionGodot\data\campaign_story.json
```

Sectors include `briefing`, `clear`, `radio`, `env` (Fringe props are densest in Godot `env_set.gd`).
