extends Node
class_name TimeRewind
## Grid Stutter + Blackout Rewind.

signal rewind_used
signal stutter_changed(active: bool)

const SLOW_SCALE := 0.35
const PARRY_SLOW_FRAMES := 42
const HOLD_EXTEND := 3
const METER_DRAIN := 0.55
const METER_REGEN := 0.22
const METER_MAX := 100.0
const BUFFER_FRAMES := 90
const REWIND_FRAMES := 90
const FLASH_FRAMES := 15

var can_rewind: bool = true
var rewind_charges: int = 1
var rewind_max: int = 1
var slow_meter: float = METER_MAX
var stutter_active: bool = false
var hold_stutter: bool = false
var slow_frames: int = 0
var afterimage_frames: int = 0
var echo_bonus: int = 0

var _buffer: Array = []
var _host: Node3D
var _combat: Node
var _lanes
var _frame_accum: float = 0.0
var _base_time_scale: float = 1.0


func setup(host: Node3D, combat: Node, lanes) -> void:
	_host = host
	_combat = combat
	_lanes = lanes
	_apply_loadout()


func _apply_loadout() -> void:
	# Vertical slice: always allow at least one rewind charge for demos.
	can_rewind = true
	rewind_max = 1
	var save = get_node_or_null("/root/SaveGame")
	if save and "rewind_cell" in save.equipped_perks:
		rewind_max += 1
	rewind_charges = rewind_max
	echo_bonus = 10 if (save and "chronoscope" in save.equipped_perks) else 0


func set_stutter_held(held: bool) -> void:
	hold_stutter = held


func trigger_parry_slow() -> void:
	slow_frames = maxi(slow_frames, PARRY_SLOW_FRAMES)
	afterimage_frames = maxi(afterimage_frames, 28)
	_set_stutter(true)


func try_rewind() -> bool:
	if not can_rewind or rewind_charges <= 0 or _buffer.size() < 2:
		return false
	var back := mini(REWIND_FRAMES, _buffer.size() - 1)
	var snap: Dictionary = _buffer[_buffer.size() - 1 - back]
	if _host:
		_host.global_transform = snap["xform"]
	if _combat and _combat.has_method("restore_snapshot"):
		_combat.restore_snapshot(snap)
	if _lanes:
		_lanes.lane_index = int(snap.get("lane", 2))
		_lanes.snap(true)
		_lanes.apply_scale()
	rewind_charges -= 1
	slow_frames = 0
	stutter_active = false
	afterimage_frames = FLASH_FRAMES
	Engine.time_scale = 1.0
	rewind_used.emit()
	stutter_changed.emit(false)
	return true


func showing_afterimages() -> bool:
	return stutter_active or afterimage_frames > 0


func afterimage_xform() -> Transform3D:
	if _buffer.size() < 5:
		return _host.global_transform if _host else Transform3D.IDENTITY
	return _buffer[_buffer.size() - 5]["xform"]


func _fx():
	return get_node_or_null("/root/CombatFX")


func _physics_process(delta: float) -> void:
	var fx = _fx()
	if fx and fx.is_hitstopped():
		return
	var frame := 1.0 / 60.0
	_frame_accum += delta
	while _frame_accum >= frame:
		_frame_accum -= frame
		_tick_frame()
	_apply_dilation()


func _tick_frame() -> void:
	if hold_stutter and slow_meter > 0.0:
		slow_meter = maxf(0.0, slow_meter - METER_DRAIN)
		slow_frames = maxi(slow_frames, HOLD_EXTEND)
		afterimage_frames = maxi(afterimage_frames, 8)
	else:
		slow_meter = minf(METER_MAX, slow_meter + METER_REGEN)

	var want := slow_frames > 0 or (hold_stutter and slow_meter > 0.0)
	_set_stutter(want)

	if slow_frames > 0:
		slow_frames -= 1
	if afterimage_frames > 0:
		afterimage_frames -= 1

	if _host == null or _combat == null:
		return
	var snap := {
		"xform": _host.global_transform,
		"hp": _combat.hp if "hp" in _combat else 100.0,
		"max_hp": _combat.max_hp if "max_hp" in _combat else 100.0,
		"lane": _lanes.lane_index if _lanes else 2,
		"facing": _combat.facing if "facing" in _combat else 1,
		"weapon": _combat.weapon if "weapon" in _combat else "sword",
	}
	_buffer.append(snap)
	while _buffer.size() > BUFFER_FRAMES:
		_buffer.pop_front()


func _set_stutter(active: bool) -> void:
	if stutter_active == active:
		return
	stutter_active = active
	stutter_changed.emit(active)


func _apply_dilation() -> void:
	var fx = _fx()
	if fx and fx.is_hitstopped():
		return
	if stutter_active:
		Engine.time_scale = SLOW_SCALE
	else:
		Engine.time_scale = 1.0
