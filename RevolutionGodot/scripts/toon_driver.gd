extends Node
class_name ToonDriver
## Pushes hurt_flash / chronal_rim / lane_tint onto toon ShaderMaterials.

var hurt_flash: float = 0.0
var chronal_rim: float = 0.0
var lane_tint: float = 1.0

var _meshes: Array[MeshInstance3D] = []
var _combat
var _lanes
var _time


func setup(root: Node3D, combat, lanes, time_rewind = null) -> void:
	_combat = combat
	_lanes = lanes
	_time = time_rewind
	_meshes.clear()
	_collect_meshes(root)
	for m in _meshes:
		_ensure_shader(m)


func _collect_meshes(n: Node) -> void:
	if n is MeshInstance3D:
		var mi := n as MeshInstance3D
		if not String(mi.name).begins_with("Ghost"):
			_meshes.append(mi)
	for c in n.get_children():
		_collect_meshes(c)


func _ensure_shader(mi: MeshInstance3D) -> void:
	var mat := mi.get_active_material(0)
	if mat is ShaderMaterial:
		return
	var sm := ShaderMaterial.new()
	sm.shader = load("res://shaders/toon.gdshader")
	var outline := ShaderMaterial.new()
	outline.shader = load("res://shaders/outline.gdshader")
	sm.next_pass = outline
	if mat is StandardMaterial3D:
		sm.set_shader_parameter("albedo", (mat as StandardMaterial3D).albedo_color)
	mi.material_override = sm


func _process(_delta: float) -> void:
	hurt_flash = _combat.hurt_flash if _combat else 0.0
	lane_tint = _lanes.lane_tint() if _lanes else 1.0
	chronal_rim = 0.0
	if _time:
		if _time.stutter_active:
			chronal_rim = 1.0
		elif _time.showing_afterimages():
			chronal_rim = 0.55
	for m in _meshes:
		var mat := m.material_override
		if mat is ShaderMaterial:
			var sm := mat as ShaderMaterial
			sm.set_shader_parameter("hurt_flash", hurt_flash)
			sm.set_shader_parameter("chronal_rim", chronal_rim)
			sm.set_shader_parameter("lane_tint", lane_tint)
