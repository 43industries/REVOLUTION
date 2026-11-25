extends CanvasLayer

@onready var hp_bar: ProgressBar = $Root/HPBar
@onready var hp_text: Label = $Root/HPText
@onready var weapon_text: Label = $Root/WeaponText
@onready var scrap_text: Label = $Root/ScrapText
@onready var lane_text: Label = $Root/LaneText
@onready var stutter_bar: ProgressBar = $Root/StutterBar
@onready var rewind_text: Label = $Root/RewindText
@onready var kills_text: Label = $Root/KillsText
@onready var hint_text: Label = $Root/HintText
@onready var banner: Label = $Root/Banner


func _ready() -> void:
	hint_text.text = "Q/E depth  ·  Shift block/parry  ·  S dodge  ·  T slow  ·  R rewind"
	var flow = get_node_or_null("/root/GameFlow")
	if flow:
		flow.state_changed.connect(_on_flow)
	banner.visible = false


func _process(_delta: float) -> void:
	var ash := get_tree().get_first_node_in_group("player")
	if ash == null:
		return
	var combat = ash.get_node_or_null("Combat")
	var lanes = ash.get_node_or_null("WLane")
	var tr = ash.get_node_or_null("TimeRewind")
	if combat == null:
		return

	hp_bar.max_value = combat.max_hp
	hp_bar.value = combat.hp
	hp_text.text = "HP %d/%d" % [int(combat.hp), int(combat.max_hp)]
	match combat.weapon:
		"bow":
			weapon_text.text = "[2] BOW"
		"crossbow":
			weapon_text.text = "[3] XBOW"
		_:
			weapon_text.text = "[1] SWORD"
	var save = get_node_or_null("/root/SaveGame")
	scrap_text.text = "SCRAP: %d" % (save.scrap if save else 0)
	kills_text.text = "KILLS: %d" % combat.kills

	if lanes:
		var parts: PackedStringArray = []
		var labels: Array = lanes.LABELS
		for i in lanes.LANE_COUNT:
			var label: String = String(labels[i])
			parts.append("[%s]" % label if i == lanes.lane_index else label)
		lane_text.text = "  ".join(parts)

	if tr:
		stutter_bar.max_value = tr.METER_MAX
		stutter_bar.value = tr.slow_meter
		rewind_text.text = "REWIND %d/%d" % [tr.rewind_charges, tr.rewind_max]


func _on_flow(_old_state, new_state) -> void:
	var flow = get_node_or_null("/root/GameFlow")
	if flow == null:
		return
	# StoryUI owns briefing/clear/death/win text; HUD only shows pause.
	if new_state == flow.State.PAUSED:
		banner.visible = true
		banner.text = "PAUSED"
	else:
		banner.visible = false
	var combat_hud: bool = new_state == flow.State.PLAYING or new_state == flow.State.PAUSED
	$Root/HPBar.visible = combat_hud
	$Root/HPText.visible = combat_hud
	$Root/WeaponText.visible = combat_hud
	$Root/ScrapText.visible = combat_hud
	$Root/LaneText.visible = combat_hud
	$Root/StutterBar.visible = combat_hud
	$Root/RewindText.visible = combat_hud
	$Root/KillsText.visible = combat_hud
	$Root/HintText.visible = combat_hud
