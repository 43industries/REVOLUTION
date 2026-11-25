extends Node
## Parity with revolution_save.json combat meta.

const USER_PATH := "user://revolution_save.json"

var high_score: int = 0
var checkpoint_wave: int = -1
var map_unlock: int = 0
var story_seen: Array = []
var sectors_cleared: Array = []
var scrap: int = 0
var owned_upgrades: Array = ["block"]
var equipped_perks: Array = []
var equipped_gear: Dictionary = {"blade": "standard", "quiver": "standard", "frame": "standard"}


func _ready() -> void:
	load_or_create()


func load_or_create() -> void:
	if FileAccess.file_exists(USER_PATH):
		_read_path(USER_PATH)
		return
	var sibling := ProjectSettings.globalize_path("res://").get_base_dir().path_join("../revolution_save.json")
	if FileAccess.file_exists(sibling):
		_read_path(sibling)
		write()
		return
	owned_upgrades = ["block"]
	write()


func _read_path(path: String) -> void:
	var f := FileAccess.open(path, FileAccess.READ)
	if f == null:
		return
	var data = JSON.parse_string(f.get_as_text())
	f.close()
	if typeof(data) != TYPE_DICTIONARY:
		return
	high_score = int(data.get("high_score", 0))
	var ck = data.get("checkpoint_wave", null)
	checkpoint_wave = int(ck) if ck != null else -1
	map_unlock = int(data.get("map_unlock", 0))
	scrap = int(data.get("scrap", 0))
	story_seen = data.get("story_seen", [])
	sectors_cleared = data.get("sectors_cleared", [])
	owned_upgrades = data.get("owned_upgrades", ["block"])
	equipped_perks = data.get("equipped_perks", [])
	var gear = data.get("equipped_gear", {})
	if typeof(gear) == TYPE_DICTIONARY:
		equipped_gear = gear


func write() -> void:
	var payload := {
		"high_score": high_score,
		"checkpoint_wave": checkpoint_wave if checkpoint_wave >= 0 else null,
		"map_unlock": map_unlock,
		"scrap": scrap,
		"story_seen": story_seen,
		"sectors_cleared": sectors_cleared,
		"owned_upgrades": owned_upgrades,
		"equipped_perks": equipped_perks,
		"equipped_gear": equipped_gear,
	}
	var f := FileAccess.open(USER_PATH, FileAccess.WRITE)
	if f:
		f.store_string(JSON.stringify(payload, "\t"))
		f.close()


func combat_tier() -> int:
	return mini(sectors_cleared.size(), 6)


func has_upgrade(id: String) -> bool:
	return id in owned_upgrades


func grant_scrap(amount: int) -> void:
	scrap += amount
	write()
