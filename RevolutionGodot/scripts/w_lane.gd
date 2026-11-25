extends Node
class_name WLane
## Discrete W-axis depth lanes FAR→NEAR.

signal lane_changed(old_lane: int, new_lane: int)

const LABELS := ["FAR", "BACK", "MID", "FORE", "NEAR"]
const LANE_COUNT := 5
const STEP_CD := 20
const GHOST_FRAMES := 18
const FAR_SCALE := 0.72
const NEAR_SCALE := 1.08
const LANE_SPACING := 0.85

var lane_index: int = 2
var step_cd: int = 0
var ghost_frames: int = 0
var last_step_delta: int = 0
var _host: Node3D
var _frame_accum: float = 0.0


func setup(host: Node3D) -> void:
	_host = host
	snap(true)
	apply_scale()


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
		if step_cd > 0:
			step_cd -= 1
		if ghost_frames > 0:
			ghost_frames -= 1


func try_step(delta_lane: int) -> bool:
	if delta_lane == 0 or step_cd > 0:
		return false
	var old := lane_index
	var nxt := clampi(lane_index + delta_lane, 0, LANE_COUNT - 1)
	if nxt == old:
		return false
	lane_index = nxt
	last_step_delta = delta_lane
	step_cd = STEP_CD
	ghost_frames = GHOST_FRAMES
	snap(false)
	apply_scale()
	lane_changed.emit(old, lane_index)
	return true


func depth_scale() -> float:
	var t := float(lane_index) / float(LANE_COUNT - 1)
	return lerpf(FAR_SCALE, NEAR_SCALE, t)


func lane_tint() -> float:
	var t := float(lane_index) / float(LANE_COUNT - 1)
	return lerpf(0.68, 1.0, t)


func lane_z() -> float:
	var mid := LANE_COUNT / 2
	return float(lane_index - mid) * LANE_SPACING


func can_hit(other_lane: int, all_lanes: bool = false, max_gap: int = 1) -> bool:
	if all_lanes:
		return true
	return absi(lane_index - other_lane) <= max_gap


func showing_ghost() -> bool:
	return ghost_frames > 0


func ghost_lane() -> int:
	return clampi(lane_index - last_step_delta, 0, LANE_COUNT - 1)


func ghost_z() -> float:
	var mid := LANE_COUNT / 2
	return float(ghost_lane() - mid) * LANE_SPACING


func snap(instant: bool) -> void:
	if _host == null:
		return
	var p := _host.global_position
	p.z = lane_z()
	if instant:
		_host.global_position = p
	else:
		_host.global_position = p


func apply_scale() -> void:
	if _host == null:
		return
	var s := depth_scale()
	_host.scale = Vector3(s, s, s)
