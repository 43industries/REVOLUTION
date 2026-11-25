extends Node3D
class_name PlaceholderBody
## Capsule + sphere humanoid with sword socket and translucent ghost copy.

const SOCKET_WEAPON_R := "weapon_r"
const SOCKET_WEAPON_L := "weapon_l"
const SOCKET_SPINE := "spine_03"
const SOCKET_HEAD := "head"

var body: MeshInstance3D
var head: MeshInstance3D
var sword: MeshInstance3D
var ghost: Node3D
var albedo: Color = Color(0.86, 0.82, 0.75)


func build(skin: Color = Color(0.86, 0.82, 0.75)) -> void:
	albedo = skin
	# Clear previous
	for c in get_children():
		c.queue_free()

	body = _mesh_capsule(Vector3(0, 0.95, 0), Vector3(0.55, 1.1, 0.55), skin)
	body.name = "Body"
	add_child(body)

	head = _mesh_sphere(Vector3(0, 1.85, 0), 0.28, skin.lightened(0.08))
	head.name = SOCKET_HEAD
	add_child(head)

	var spine := Marker3D.new()
	spine.name = SOCKET_SPINE
	spine.position = Vector3(0, 1.35, 0)
	add_child(spine)

	var hand_r := Marker3D.new()
	hand_r.name = SOCKET_WEAPON_R
	hand_r.position = Vector3(0.45, 1.15, 0.1)
	add_child(hand_r)

	var hand_l := Marker3D.new()
	hand_l.name = SOCKET_WEAPON_L
	hand_l.position = Vector3(-0.45, 1.15, 0.1)
	add_child(hand_l)

	sword = _mesh_box(Vector3(0.55, 0.15, 0.05), Color(0.75, 0.78, 0.88))
	sword.name = "Sword"
	hand_r.add_child(sword)
	sword.position = Vector3(0.35, 0, 0)
	sword.rotation_degrees = Vector3(0, 0, 20)

	ghost = Node3D.new()
	ghost.name = "Ghost"
	ghost.visible = false
	add_child(ghost)
	var gb := _mesh_capsule(Vector3(0, 0.95, 0), Vector3(0.55, 1.1, 0.55), Color(0.2, 0.85, 1.0, 0.35))
	gb.name = "GhostBody"
	ghost.add_child(gb)
	var gh := _mesh_sphere(Vector3(0, 1.85, 0), 0.28, Color(0.2, 0.85, 1.0, 0.35))
	gh.name = "GhostHead"
	ghost.add_child(gh)


func get_sword() -> MeshInstance3D:
	return sword


func show_ghost_at(global_pos: Vector3, scale_v: Vector3) -> void:
	if ghost == null:
		return
	ghost.visible = true
	ghost.global_position = global_pos
	ghost.scale = scale_v


func hide_ghost() -> void:
	if ghost:
		ghost.visible = false


func _mesh_capsule(pos: Vector3, size: Vector3, color: Color) -> MeshInstance3D:
	var mi := MeshInstance3D.new()
	var mesh := CapsuleMesh.new()
	mesh.radius = size.x * 0.35
	mesh.height = size.y
	mi.mesh = mesh
	mi.position = pos
	mi.material_override = _std(color)
	return mi


func _mesh_sphere(pos: Vector3, radius: float, color: Color) -> MeshInstance3D:
	var mi := MeshInstance3D.new()
	var mesh := SphereMesh.new()
	mesh.radius = radius
	mesh.height = radius * 2.0
	mi.mesh = mesh
	mi.position = pos
	mi.material_override = _std(color)
	return mi


func _mesh_box(size: Vector3, color: Color) -> MeshInstance3D:
	var mi := MeshInstance3D.new()
	var mesh := BoxMesh.new()
	mesh.size = size
	mi.mesh = mesh
	mi.material_override = _std(color)
	return mi


func _std(color: Color) -> StandardMaterial3D:
	var m := StandardMaterial3D.new()
	m.albedo_color = color
	if color.a < 0.99:
		m.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	return m
