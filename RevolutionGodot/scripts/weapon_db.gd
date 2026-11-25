extends RefCounted
class_name WeaponDB
## Loads data/WeaponProfiles.json — ports WEAPON_PROFILES from revolution.py.

const PX_TO_M := 0.028
const PATH := "res://data/WeaponProfiles.json"

var profiles: Dictionary = {}


func _init() -> void:
	if not _load_json():
		_fill_defaults()


func _load_json() -> bool:
	if not FileAccess.file_exists(PATH):
		return false
	var f := FileAccess.open(PATH, FileAccess.READ)
	if f == null:
		return false
	var data = JSON.parse_string(f.get_as_text())
	f.close()
	if typeof(data) != TYPE_DICTIONARY:
		return false
	profiles.clear()
	if data.has("sword"):
		profiles["sword"] = _parse_sword(data["sword"])
	if data.has("bow"):
		profiles["bow"] = _parse_bow(data["bow"])
	if data.has("crossbow"):
		profiles["crossbow"] = _parse_crossbow(data["crossbow"])
	return profiles.has("sword")


func _parse_sword(s: Dictionary) -> Dictionary:
	var moves := {}
	for id in s.get("moves", {}).keys():
		moves[id] = _parse_move(s["moves"][id], int(s.get("anim_len", 22)), int(s.get("active_lo", 9)), int(s.get("active_hi", 13)))
	return {
		"combo": s.get("combo", ["jab", "slash", "finisher"]),
		"combo_window": int(s.get("combo_window", 48)),
		"anim_len": int(s.get("anim_len", 22)),
		"cd_max": int(s.get("cd_max", 36)),
		"active_lo": int(s.get("active_lo", 9)),
		"active_hi": int(s.get("active_hi", 13)),
		"moves": moves,
	}


func _parse_bow(b: Dictionary) -> Dictionary:
	var moves := {}
	for id in b.get("melee", {}).keys():
		var m: Dictionary = b["melee"][id]
		moves[id] = _parse_move(m, int(m.get("anim_len", 16)), int(m.get("active_lo", 6)), int(m.get("active_hi", 9)))
	return {"moves": moves}


func _parse_crossbow(c: Dictionary) -> Dictionary:
	var moves := {}
	for id in c.get("melee", {}).keys():
		var m: Dictionary = c["melee"][id]
		moves[id] = _parse_move(m, int(m.get("anim_len", 18)), int(m.get("active_lo", 7)), int(m.get("active_hi", 10)))
	return {"moves": moves}


func _parse_move(m: Dictionary, anim_len: int, alo: int, ahi: int) -> Dictionary:
	var dmg = m.get("dmg", [16, 24])
	var shake = m.get("shake", [7, 9])
	return {
		"reach": float(m.get("reach", 42)) * PX_TO_M,
		"dmg_min": float(dmg[0]),
		"dmg_max": float(dmg[1]),
		"kb": float(m.get("kb", 5.0)),
		"freeze": int(m.get("freeze", 3)),
		"shake_mag": float(shake[0]),
		"shake_frames": int(shake[1]),
		"lunge": float(m.get("lunge", 1.0)),
		"anim_len": anim_len,
		"active_lo": alo,
		"active_hi": ahi,
		"multi": int(m.get("multi", 1)),
		"trip": bool(m.get("trip", false)),
		"break_block": bool(m.get("break_block", false)),
	}


func _fill_defaults() -> void:
	profiles = {
		"sword": {
			"combo": ["jab", "slash", "finisher"],
			"combo_window": 48,
			"anim_len": 22,
			"cd_max": 36,
			"active_lo": 9,
			"active_hi": 13,
			"moves": {
				"jab": {"reach": 42 * PX_TO_M, "dmg_min": 16, "dmg_max": 24, "kb": 5.2, "freeze": 3, "shake_mag": 7, "shake_frames": 9, "lunge": 0.85, "anim_len": 22, "active_lo": 9, "active_hi": 13, "multi": 1, "trip": false, "break_block": false},
				"slash": {"reach": 48 * PX_TO_M, "dmg_min": 22, "dmg_max": 34, "kb": 6.8, "freeze": 3, "shake_mag": 7, "shake_frames": 9, "lunge": 1.05, "anim_len": 22, "active_lo": 9, "active_hi": 13, "multi": 1, "trip": false, "break_block": false},
				"finisher": {"reach": 54 * PX_TO_M, "dmg_min": 28, "dmg_max": 42, "kb": 8.5, "freeze": 5, "shake_mag": 10, "shake_frames": 12, "lunge": 1.35, "anim_len": 22, "active_lo": 9, "active_hi": 13, "multi": 1, "trip": false, "break_block": false},
			},
		}
	}


func get_move(weapon: String, move_id: String) -> Dictionary:
	if not profiles.has(weapon):
		return {}
	var moves: Dictionary = profiles[weapon].get("moves", {})
	return moves.get(move_id, {})


func get_profile(weapon: String) -> Dictionary:
	return profiles.get(weapon, {})
