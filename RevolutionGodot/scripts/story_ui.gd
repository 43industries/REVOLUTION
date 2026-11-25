extends CanvasLayer
## Briefing / clear / death / victory overlay driven by StoryDB + GameFlow.

@onready var panel: ColorRect = $Root/Dim
@onready var title_label: Label = $Root/Title
@onready var body_label: Label = $Root/Body
@onready var hint_label: Label = $Root/Hint
@onready var radio_label: Label = $Root/Radio

var _line_idx: int = 0
var _lines: Array = []
var _mode: String = ""  # briefing | clear | death | victory


func _ready() -> void:
	layer = 30
	process_mode = Node.PROCESS_MODE_ALWAYS
	var flow = get_node_or_null("/root/GameFlow")
	if flow:
		flow.state_changed.connect(_on_flow)
		# Start campaign briefing immediately.
		if flow.state == flow.State.INTRO or flow.state == flow.State.PLAYING:
			flow.begin_campaign(0)
	_refresh_visibility()


func _process(_delta: float) -> void:
	var flow = get_node_or_null("/root/GameFlow")
	if flow == null:
		return
	if flow.state == flow.State.BRIEFING or flow.state == flow.State.CLEAR \
			or flow.state == flow.State.GAME_OVER or flow.state == flow.State.WIN:
		if Input.is_action_just_pressed("attack") or Input.is_action_just_pressed("jump") \
				or Input.is_action_just_pressed("ui_accept"):
			_advance()


func _on_flow(_old, new_state) -> void:
	var flow = get_node_or_null("/root/GameFlow")
	var story = get_node_or_null("/root/StoryDB")
	if flow == null or story == null:
		return
	if new_state == flow.State.BRIEFING:
		_mode = "briefing"
		_lines = story.briefing_lines(flow.active_sector)
		_line_idx = 0
		title_label.text = story.sector_title(flow.active_sector).to_upper()
		_show_lines()
	elif new_state == flow.State.CLEAR:
		_mode = "clear"
		_lines = [story.clear_line(flow.active_sector)]
		_line_idx = 0
		title_label.text = "SECTOR CLEAR"
		_show_lines()
	elif new_state == flow.State.GAME_OVER:
		_mode = "death"
		var cleared := 0
		var save = get_node_or_null("/root/SaveGame")
		if save:
			cleared = save.sectors_cleared.size()
		_lines = [story.death_line_for_progress(cleared)]
		_line_idx = 0
		title_label.text = "BLACKOUT"
		_show_lines()
	elif new_state == flow.State.WIN:
		_mode = "victory"
		var sec: Dictionary = story.get_sector(flow.active_sector)
		var after := String(sec.get("blurb_after", ""))
		if after.is_empty():
			_lines = [story.victory_line()]
		else:
			_lines = [after, "Chalk north. The story continues."]
		_line_idx = 0
		title_label.text = "TRAIL OPEN"
		_show_lines()
	_refresh_visibility()


func _advance() -> void:
	var flow = get_node_or_null("/root/GameFlow")
	if flow == null:
		return
	if _line_idx < _lines.size() - 1:
		_line_idx += 1
		_show_lines()
		return
	match _mode:
		"briefing":
			flow.advance_from_briefing()
		"clear":
			flow.advance_from_clear()
		"death", "victory":
			# Restart fringe briefing for the slice loop.
			flow.begin_campaign(0)


func _show_lines() -> void:
	var shown: PackedStringArray = []
	for i in range(_line_idx + 1):
		if i < _lines.size():
			shown.append(String(_lines[i]))
	body_label.text = "\n\n".join(shown)
	hint_label.text = "ENTER / CLICK  —  continue"


func _refresh_visibility() -> void:
	var flow = get_node_or_null("/root/GameFlow")
	var show := false
	if flow:
		show = flow.state in [flow.State.BRIEFING, flow.State.CLEAR, flow.State.GAME_OVER, flow.State.WIN]
	panel.visible = show
	title_label.visible = show
	body_label.visible = show
	hint_label.visible = show
	if not show:
		radio_label.visible = false


func show_radio(text: String, duration: float = 4.0) -> void:
	radio_label.text = text
	radio_label.visible = true
	var tw := create_tween()
	tw.tween_interval(duration)
	tw.tween_callback(func():
		radio_label.visible = false
	)
