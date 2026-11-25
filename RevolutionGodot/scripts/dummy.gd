extends CharacterBody3D
## Melee dummy for the vertical slice.

const SPEED := 3.6
const ATTACK_RANGE := 1.6
const AGGRO := 9.0

@onready var visuals = $Visuals
@onready var combat = $Combat
@onready var lanes = $WLane
@onready var toon = $ToonDriver

var gravity: float = ProjectSettings.get_setting("physics/3d/default_gravity")
var attack_cd: float = 0.0
var dead: bool = false


func _ready() -> void:
	visuals.build(Color(0.72, 0.28, 0.22))
	lanes.setup(self)
	combat.setup(self, lanes, "enemy", visuals.get_sword())
	combat.max_hp = 60.0
	combat.hp = 60.0
	combat.can_block = false
	combat.can_dodge = false
	combat.can_parry = false
	toon.setup(visuals, combat, lanes, null)
	combat.died.connect(_on_died)
	add_to_group("enemy")


func _physics_process(delta: float) -> void:
	var flow = get_node_or_null("/root/GameFlow")
	if dead or (flow and flow.state != flow.State.PLAYING):
		return
	var fx = get_node_or_null("/root/CombatFX")
	if fx and fx.is_hitstopped():
		return

	if not is_on_floor():
		velocity.y -= gravity * delta

	if attack_cd > 0.0:
		attack_cd -= delta

	var player := get_tree().get_first_node_in_group("player") as Node3D
	if player == null:
		move_and_slide()
		return

	var to_p := player.global_position - global_position
	var dist := Vector2(to_p.x, to_p.z).length()
	if dist > AGGRO:
		velocity.x = move_toward(velocity.x, 0.0, SPEED)
		move_and_slide()
		return

	combat.facing = 1 if to_p.x >= 0.0 else -1
	visuals.rotation.y = 0.0 if combat.facing > 0 else PI

	# Match player lane
	var p_lanes = player.get_node_or_null("WLane")
	if p_lanes and p_lanes.lane_index != lanes.lane_index:
		lanes.try_step(clampi(p_lanes.lane_index - lanes.lane_index, -1, 1))

	if dist > ATTACK_RANGE:
		velocity.x = signf(to_p.x) * SPEED
	else:
		velocity.x = 0.0
		if attack_cd <= 0.0 and not combat.is_attacking():
			combat.try_attack()
			attack_cd = 1.1

	move_and_slide()


func _on_died() -> void:
	dead = true
	velocity = Vector3.ZERO
	collision_layer = 0
	collision_mask = 0
	var flow = get_node_or_null("/root/GameFlow")
	if flow:
		flow.notify_sector_cleared()
	var tw := create_tween()
	tw.tween_property(self, "scale", Vector3(0.01, 0.01, 0.01), 0.45)
	tw.finished.connect(queue_free)
	var save = get_node_or_null("/root/SaveGame")
	if save:
		save.grant_scrap(5)
