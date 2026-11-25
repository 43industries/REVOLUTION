extends Node
## Hitstop + camera shake — ports COMBAT_HITSTOP / COMBAT_SHAKE from revolution.py.

const FRAME := 1.0 / 60.0

var hitstop_frames: int = 0
var shake_frames: int = 0
var shake_mag: float = 0.0
var _camera: Camera3D
var _cam_base: Vector3 = Vector3.ZERO
var _frame_accum: float = 0.0


func register_camera(cam: Camera3D) -> void:
	_camera = cam
	if _camera:
		_cam_base = _camera.position


func hitstop(frames: int = 3) -> void:
	hitstop_frames = maxi(hitstop_frames, frames)
	Engine.time_scale = 0.05 if frames > 0 else 1.0


func shake(magnitude: float = 6.0, frames: int = 10) -> void:
	shake_frames = maxi(shake_frames, frames)
	shake_mag = maxf(shake_mag, magnitude)


func is_hitstopped() -> bool:
	return hitstop_frames > 0


func _process(delta: float) -> void:
	_frame_accum += delta / maxf(Engine.time_scale, 0.001)
	while _frame_accum >= FRAME:
		_frame_accum -= FRAME
		if hitstop_frames > 0:
			hitstop_frames -= 1
			if hitstop_frames <= 0:
				Engine.time_scale = 1.0
		if shake_frames > 0:
			shake_frames -= 1
			if shake_frames <= 0:
				shake_mag = 0.0
	_apply_shake()


func _apply_shake() -> void:
	if _camera == null:
		return
	if shake_frames <= 0 or shake_mag <= 0.0:
		_camera.position = _cam_base
		return
	var m := maxf(0.02, shake_mag * 0.004 * float(shake_frames) / float(shake_frames + 6))
	_camera.position = _cam_base + Vector3(
		randf_range(-m, m),
		randf_range(-m * 0.5, m * 0.5),
		randf_range(-m * 0.25, m * 0.25)
	)
