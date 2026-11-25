extends Node3D

const TERRAIN_GLB := "res://assets/terrain/fringe/fringe_terrain.glb"
const PROPS_GLB := "res://assets/terrain/fringe/fringe_props.glb"
const TERRAIN_Y_OFFSET := -0.35

@onready var camera: Camera3D = $CameraRig/Camera3D
@onready var camera_rig: Node3D = $CameraRig
@onready var env_set: Node3D = $EnvSet
@onready var story_ui = $StoryUI
@onready var radio: Node = $RadioChatter
@onready var terrain_root: Node3D = $TerrainRoot
@onready var props_root: Node3D = $PropsRoot
@onready var ground_mesh: MeshInstance3D = $Ground/Mesh
@onready var ruins: Node3D = $Ruins


func _ready() -> void:
	_spawn_fringe_terrain()

	var fx = get_node_or_null("/root/CombatFX")
	if fx:
		fx.register_camera(camera)

	var flow = get_node_or_null("/root/GameFlow")
	var story = get_node_or_null("/root/StoryDB")
	if flow:
		flow.sector_started.connect(_on_sector_started)
		if flow.state != flow.State.BRIEFING:
			flow.begin_campaign(0)
	if story and env_set:
		env_set.build_for_sector(story.env_id(0))
	if radio and story_ui:
		radio.setup(story_ui)


func _spawn_fringe_terrain() -> void:
	# Clear previous instances if any.
	for c in terrain_root.get_children():
		c.queue_free()
	for c in props_root.get_children():
		c.queue_free()

	var has_terrain := ResourceLoader.exists(TERRAIN_GLB)
	if has_terrain:
		var packed: PackedScene = load(TERRAIN_GLB) as PackedScene
		if packed:
			var terrain: Node3D = packed.instantiate() as Node3D
			terrain.name = "FringeTerrain"
			terrain.position = Vector3(0.0, TERRAIN_Y_OFFSET, 0.0)
			terrain_root.add_child(terrain)
			# Flat Ground StaticBody stays for fight-lane collision (Intel HD safe).
			if ground_mesh:
				ground_mesh.visible = false
			if ruins:
				ruins.visible = false
		else:
			_use_flat_ground_fallback()
	else:
		_use_flat_ground_fallback()

	if ResourceLoader.exists(PROPS_GLB):
		var props_packed: PackedScene = load(PROPS_GLB) as PackedScene
		if props_packed:
			var props: Node3D = props_packed.instantiate() as Node3D
			props.name = "FringeProps"
			props.position = Vector3(0.0, 0.0, 0.0)
			props_root.add_child(props)


func _use_flat_ground_fallback() -> void:
	if ground_mesh:
		ground_mesh.visible = true
		# Warm dirt tone so flat ground still reads frontier when glTF missing.
		var mat := StandardMaterial3D.new()
		mat.albedo_color = Color(0.38, 0.28, 0.18)
		mat.roughness = 0.95
		ground_mesh.material_override = mat
	if ruins:
		ruins.visible = false


func _on_sector_started(sector_index: int) -> void:
	var story = get_node_or_null("/root/StoryDB")
	if story and env_set:
		env_set.build_for_sector(story.env_id(sector_index))
	# Reset fighters for sector start
	var ash := get_tree().get_first_node_in_group("player")
	if ash and ash.has_node("Combat"):
		ash.global_position = Vector3(-2, 0.1, 0)
		ash.get_node("Combat").hp = ash.get_node("Combat").max_hp
	# Respawn dummy if missing
	if get_tree().get_first_node_in_group("enemy") == null:
		var packed := load("res://scenes/dummy.tscn")
		if packed:
			var d = packed.instantiate()
			d.name = "Dummy"
			d.position = Vector3(4, 0, 0)
			add_child(d)


func _process(_delta: float) -> void:
	var ash := get_tree().get_first_node_in_group("player") as Node3D
	if ash == null:
		return
	var target := Vector3(ash.global_position.x, 1.6, 6.5)
	camera_rig.global_position = camera_rig.global_position.lerp(target, 0.12)
