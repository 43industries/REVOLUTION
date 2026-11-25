extends Node
## Plays sector radio / memory lines during combat.

var _timer: float = 8.0
var _idx: int = 0
var _story_ui: Node


func setup(story_ui: Node) -> void:
	_story_ui = story_ui
	_timer = 6.0
	_idx = 0


func _physics_process(delta: float) -> void:
	var flow = get_node_or_null("/root/GameFlow")
	if flow == null or not flow.combat_enabled():
		return
	_timer -= delta
	if _timer > 0.0:
		return
	_timer = randf_range(10.0, 16.0)
	var story = get_node_or_null("/root/StoryDB")
	if story == null or _story_ui == null:
		return
	var lines: Array = story.radio_lines(flow.active_sector)
	if lines.is_empty():
		return
	var text := String(lines[_idx % lines.size()])
	_idx += 1
	if _story_ui.has_method("show_radio"):
		_story_ui.show_radio(text, 4.5)
