extends Node
## Shared campaign story — loads data/campaign_story.json (mirror of ../story/).

const RES_PATH := "res://data/campaign_story.json"

var hero_name: String = "Ash Trace"
var hero_lost_name: String = "Mira"
var prologue: Array = []
var sectors: Array = []
var monroe_taunts: Array = []
var death_lines: Array = []
var victory_lines: Array = []
var current_sector: int = 0
var _loaded: bool = false


func _ready() -> void:
	reload()


func reload() -> void:
	var data = _read_json(RES_PATH)
	if data == null:
		var sibling := ProjectSettings.globalize_path("res://").get_base_dir().path_join("../story/campaign_story.json")
		data = _read_json_abs(sibling)
	if typeof(data) != TYPE_DICTIONARY:
		push_warning("StoryDB: campaign_story.json missing — using stubs")
		_fill_stub()
		_loaded = true
		return
	hero_name = String(data.get("hero_name", hero_name))
	hero_lost_name = String(data.get("hero_lost_name", hero_lost_name))
	prologue = data.get("prologue", [])
	sectors = data.get("sectors", [])
	monroe_taunts = data.get("monroe_phase_taunts", [])
	death_lines = data.get("death_lines", [])
	victory_lines = data.get("victory_lines", [])
	_loaded = true


func _read_json(res_path: String):
	if not FileAccess.file_exists(res_path):
		return null
	var f := FileAccess.open(res_path, FileAccess.READ)
	if f == null:
		return null
	var parsed = JSON.parse_string(f.get_as_text())
	f.close()
	return parsed


func _read_json_abs(abs_path: String):
	if not FileAccess.file_exists(abs_path):
		return null
	var f := FileAccess.open(abs_path, FileAccess.READ)
	if f == null:
		return null
	var parsed = JSON.parse_string(f.get_as_text())
	f.close()
	return parsed


func _fill_stub() -> void:
	prologue = ["The lights died. The chalk remains."]
	sectors = [{
		"id": "fringe",
		"title": "The Fringe",
		"briefing": ["THE FRINGE — edge of what's left.", "Break through."],
		"clear": "The patrol breaks.",
		"radio": ["RADIO: …Militia sweep…"],
		"env": "fringe",
	}]


func sector_count() -> int:
	return sectors.size()


func get_sector(index: int = -1) -> Dictionary:
	var i := current_sector if index < 0 else index
	if i < 0 or i >= sectors.size():
		return {}
	return sectors[i]


func briefing_lines(index: int = -1) -> Array:
	var s := get_sector(index)
	return s.get("briefing", [])


func clear_line(index: int = -1) -> String:
	return String(get_sector(index).get("clear", ""))


func sector_title(index: int = -1) -> String:
	return String(get_sector(index).get("title", "Unknown"))


func radio_lines(index: int = -1) -> Array:
	return get_sector(index).get("radio", [])


func env_id(index: int = -1) -> String:
	return String(get_sector(index).get("env", "fringe"))


func death_line_for_progress(sectors_cleared: int) -> String:
	if death_lines.is_empty():
		return "The chalk outlasts me."
	return String(death_lines[mini(sectors_cleared, death_lines.size() - 1)])


func victory_line() -> String:
	if victory_lines.is_empty():
		return "Monroe is down."
	return String(victory_lines[victory_lines.size() - 1])
