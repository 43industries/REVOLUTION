extends Node3D
## Sector environment personality. Fringe uses RDR2-mood props + chalk on Gaea/Blender terrain.

const TERRAIN_GLB := "res://assets/terrain/fringe/fringe_terrain.glb"
const PROPS_GLB := "res://assets/terrain/fringe/fringe_props.glb"

var _has_terrain_asset: bool = false


func build_for_sector(env_id: String) -> void:
	for c in get_children():
		c.queue_free()
	_has_terrain_asset = ResourceLoader.exists(TERRAIN_GLB)
	match env_id:
		"fringe":
			_build_fringe()
		"dead_grid":
			_build_dead_grid()
		"ash_corridor":
			_build_ash_corridor()
		"broken_line":
			_build_broken_line()
		"iron_march":
			_build_iron_march()
		"last_gate":
			_build_last_gate()
		"philadelphia":
			_build_philadelphia()
		_:
			_build_fringe()


func _mat(color: Color) -> StandardMaterial3D:
	var m := StandardMaterial3D.new()
	m.albedo_color = color
	m.roughness = 0.92
	return m


func _box(pos: Vector3, size: Vector3, color: Color, rot_y: float = 0.0) -> MeshInstance3D:
	var mi := MeshInstance3D.new()
	var mesh := BoxMesh.new()
	mesh.size = size
	mi.mesh = mesh
	mi.position = pos
	mi.rotation.y = rot_y
	mi.material_override = _mat(color)
	add_child(mi)
	return mi


func _cylinder(pos: Vector3, radius: float, height: float, color: Color) -> MeshInstance3D:
	var mi := MeshInstance3D.new()
	var mesh := CylinderMesh.new()
	mesh.top_radius = radius
	mesh.bottom_radius = radius
	mesh.height = height
	mi.mesh = mesh
	mi.position = pos
	mi.material_override = _mat(color)
	add_child(mi)
	return mi


func _sphere(pos: Vector3, radius: float, color: Color) -> MeshInstance3D:
	var mi := MeshInstance3D.new()
	var mesh := SphereMesh.new()
	mesh.radius = radius
	mesh.height = radius * 2.0
	mi.mesh = mesh
	mi.position = pos
	mi.material_override = _mat(color)
	add_child(mi)
	return mi


func _chalk_arrow(x: float, z: float) -> void:
	var cream := Color(0.93, 0.88, 0.72)
	_box(Vector3(x, 0.06, z), Vector3(0.85, 0.03, 0.12), cream)
	_box(Vector3(x + 0.4, 0.06, z + 0.18), Vector3(0.35, 0.03, 0.09), cream, 0.65)
	_box(Vector3(x + 0.4, 0.06, z - 0.18), Vector3(0.35, 0.03, 0.09), cream, -0.65)


func _banner(x: float, z: float) -> void:
	_cylinder(Vector3(x, 1.15, z), 0.05, 2.3, Color(0.22, 0.15, 0.1))
	var cloth := _box(Vector3(x + 0.38, 1.65, z), Vector3(0.75, 0.6, 0.04), Color(0.45, 0.12, 0.1))
	cloth.rotation.z = 0.08


func _tree(x: float, z: float, scale: float = 1.0) -> void:
	_cylinder(Vector3(x, 1.1 * scale, z), 0.16 * scale, 2.2 * scale, Color(0.24, 0.15, 0.09))
	_sphere(Vector3(x, 2.5 * scale, z), 1.05 * scale, Color(0.2, 0.28, 0.12))
	_sphere(Vector3(x + 0.45 * scale, 2.3 * scale, z - 0.2 * scale), 0.7 * scale, Color(0.18, 0.26, 0.11))


func _brush(x: float, z: float) -> void:
	_sphere(Vector3(x, 0.25, z), 0.35, Color(0.28, 0.32, 0.16))
	_sphere(Vector3(x + 0.25, 0.2, z + 0.1), 0.25, Color(0.32, 0.3, 0.14))


func _fence_run(z: float, x0: float, count: int, gap_at: int = -1) -> void:
	for i in range(count):
		if i == gap_at:
			continue
		var x := x0 + i * 2.6
		var lean := 0.05 if i % 3 == 0 else 0.0
		var post := _cylinder(Vector3(x, 0.55, z), 0.06, 1.1, Color(0.28, 0.2, 0.12))
		post.rotation.z = lean
		if i < count - 1 and i + 1 != gap_at:
			_box(Vector3(x + 1.3, 0.75, z), Vector3(2.4, 0.07, 0.07), Color(0.32, 0.22, 0.14))
			_box(Vector3(x + 1.3, 0.4, z), Vector3(2.4, 0.06, 0.06), Color(0.3, 0.2, 0.12))


func _build_fringe() -> void:
	# Chalk trail (story beat — always procedural so it stays readable)
	_chalk_arrow(-1.2, 0.55)
	_chalk_arrow(0.8, -0.35)
	_chalk_arrow(3.5, 0.25)
	_chalk_arrow(6.5, -0.45)
	_chalk_arrow(10.0, 0.15)

	_banner(-5.0, -2.3)
	_banner(4.0, -2.5)
	_banner(11.0, 2.1)

	if _has_terrain_asset:
		# Terrain + prop glbs carry hills/fences/trees; add near brush + campfire only.
		for i in range(10):
			_brush(-8.0 + i * 2.0 + (i % 2) * 0.3, 2.2 + (i % 3) * 0.25)
			_brush(-6.0 + i * 2.2, -1.5 - (i % 2) * 0.2)
		_box(Vector3(1.5, 0.12, 1.6), Vector3(0.5, 0.2, 0.5), Color(0.25, 0.12, 0.06))  # fire pit stones
		var fire := OmniLight3D.new()
		fire.light_color = Color(1.0, 0.55, 0.2)
		fire.light_energy = 1.8
		fire.omni_range = 6.0
		fire.position = Vector3(1.5, 0.45, 1.6)
		add_child(fire)
		return

	# --- Procedural fallback (no glb) — full RDR2-mood silhouette kit ---
	# Dirt road strip
	_box(Vector3(0, 0.02, 0), Vector3(58, 0.04, 3.2), Color(0.42, 0.32, 0.22))
	_box(Vector3(0, 0.015, 2.4), Vector3(58, 0.03, 2.0), Color(0.3, 0.26, 0.18))
	_box(Vector3(0, 0.015, -2.4), Vector3(58, 0.03, 2.0), Color(0.28, 0.24, 0.16))

	# Far hills
	for i in range(7):
		var hx := -24.0 + i * 8.0
		var hh := 3.5 + (i % 3) * 1.4
		_box(Vector3(hx, hh * 0.5, -8.5 - (i % 2)), Vector3(9.0, hh, 3.5), Color(0.2, 0.18, 0.12))

	_fence_run(-2.7, -14.0, 12, 4)
	_fence_run(2.5, -10.0, 10, 6)

	for i in range(8):
		_tree(-16.0 + i * 5.5, -5.2 - (i % 3) * 0.6, 0.85 + (i % 2) * 0.25)
	for i in range(12):
		_brush(-10.0 + i * 2.0, 2.3 + (i % 3) * 0.2)
		_brush(-8.0 + i * 2.3, -1.4)

	# Farmstead
	_box(Vector3(15.5, 2.0, -3.4), Vector3(3.4, 4.0, 2.6), Color(0.34, 0.22, 0.15), 0.12)
	_box(Vector3(15.5, 2.2, -2.1), Vector3(0.9, 1.0, 0.12), Color(0.05, 0.04, 0.03))
	_box(Vector3(-4.0, 0.4, 2.0), Vector3(0.9, 0.8, 0.7), Color(0.4, 0.3, 0.2))
	_cylinder(Vector3(8.0, 0.45, 1.85), 0.35, 0.9, Color(0.3, 0.2, 0.12))
	_box(Vector3(0.5, 0.15, -3.0), Vector3(2.5, 0.25, 0.35), Color(0.28, 0.18, 0.12), 0.4)

	var fire2 := OmniLight3D.new()
	fire2.light_color = Color(1.0, 0.55, 0.2)
	fire2.light_energy = 1.6
	fire2.omni_range = 5.5
	fire2.position = Vector3(1.2, 0.5, 1.5)
	add_child(fire2)
	_box(Vector3(1.2, 0.12, 1.5), Vector3(0.55, 0.18, 0.55), Color(0.22, 0.12, 0.06))


func _build_dead_grid() -> void:
	for i in range(4):
		_cylinder(Vector3(-4.0 + i * 4.0, 2.4, -3.0), 0.12, 4.8, Color(0.2, 0.22, 0.25))
		_box(Vector3(-4.0 + i * 4.0, 4.6, -3.0), Vector3(2.2, 0.15, 0.15), Color(0.15, 0.16, 0.18))
	_box(Vector3(0, 0.4, 2.2), Vector3(1.4, 0.8, 1.0), Color(0.25, 0.28, 0.3))


func _build_ash_corridor() -> void:
	for i in range(5):
		_box(Vector3(-5 + i * 3.5, 0.15, -2.5 + (i % 2) * 0.4), Vector3(1.2, 0.3, 0.8), Color(0.15, 0.1, 0.08))
	_box(Vector3(4, 1.2, -2.8), Vector3(0.4, 2.4, 0.4), Color(0.2, 0.12, 0.1))


func _build_broken_line() -> void:
	_box(Vector3(-2, 0.45, 2.0), Vector3(2.2, 0.9, 1.0), Color(0.4, 0.32, 0.22))
	_cylinder(Vector3(-2.8, 0.35, 2.5), 0.35, 0.15, Color(0.15, 0.12, 0.1))
	_cylinder(Vector3(-1.2, 0.35, 2.5), 0.35, 0.15, Color(0.15, 0.12, 0.1))
	_box(Vector3(5, 0.25, -1.8), Vector3(0.7, 0.5, 0.5), Color(0.45, 0.35, 0.25))


func _build_iron_march() -> void:
	for i in range(3):
		_box(Vector3(i * 3.0, 0.7, -2.6), Vector3(1.6, 1.4, 1.2), Color(0.32, 0.28, 0.2))
	_box(Vector3(8, 0.5, 1.8), Vector3(1.5, 1.0, 0.8), Color(0.3, 0.25, 0.18))


func _build_last_gate() -> void:
	_box(Vector3(6, 1.5, 0), Vector3(0.6, 3.0, 5.0), Color(0.28, 0.24, 0.2))
	_box(Vector3(6, 3.2, 0), Vector3(1.2, 0.4, 5.2), Color(0.22, 0.18, 0.15))


func _build_philadelphia() -> void:
	_box(Vector3(10, 3.5, -3.5), Vector3(2.5, 7.0, 2.5), Color(0.18, 0.12, 0.12))
	_box(Vector3(14, 2.5, -2.5), Vector3(1.8, 5.0, 1.8), Color(0.2, 0.1, 0.1))
	_banner(8, -2.0)
