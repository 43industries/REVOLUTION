extends CharacterBody3D
## Ash Trace — player fighter.

const SPEED := 7.0
const JUMP_VELOCITY := 10.5

@onready var visuals = $Visuals
@onready var combat = $Combat
@onready var lanes = $WLane
@onready var time_rewind = $TimeRewind
@onready var toon = $ToonDriver

var gravity: float = ProjectSettings.get_setting("physics/3d/default_gravity")


func _ready() -> void:
	visuals.build(Color(0.90, 0.86, 0.78))
	lanes.setup(self)
	combat.setup(self, lanes, "player", visuals.get_sword())
	combat.max_hp = 100.0
	combat.hp = 100.0
	combat.can_block = true
	var save = get_node_or_null("/root/SaveGame")
	if save:
		combat.can_dodge = save.combat_tier() >= 1 or save.has_upgrade("dodge")
		combat.can_parry = save.combat_tier() >= 2 or save.has_upgrade("parry")
	time_rewind.setup(self, combat, lanes)
	toon.setup(visuals, combat, lanes, time_rewind)
	combat.died.connect(_on_died)
	add_to_group("player")


func _physics_process(delta: float) -> void:
	var flow = get_node_or_null("/root/GameFlow")
	if flow and flow.state == flow.State.PAUSED:
		return

	if not is_on_floor():
		velocity.y -= gravity * delta

	var can_fight: bool = flow == null or flow.combat_enabled()

	if Input.is_action_just_pressed("pause") and flow and can_fight:
		flow.toggle_pause()

	if not can_fight:
		velocity.x = move_toward(velocity.x, 0.0, SPEED)
		move_and_slide()
		return

	if Input.is_action_just_pressed("jump") and is_on_floor():
		velocity.y = JUMP_VELOCITY

	var dir := Input.get_axis("move_left", "move_right")
	if dir != 0.0:
		velocity.x = dir * SPEED
		combat.facing = 1 if dir > 0.0 else -1
		visuals.rotation.y = 0.0 if combat.facing > 0 else PI
	else:
		velocity.x = move_toward(velocity.x, 0.0, SPEED)

	if Input.is_action_just_pressed("attack"):
		combat.try_attack()
	if Input.is_action_pressed("block"):
		combat.try_block(true)
	else:
		combat.try_block(false)
	if Input.is_action_just_pressed("dodge"):
		combat.try_dodge()
	if Input.is_action_just_pressed("lane_left"):
		lanes.try_step(-1)
	if Input.is_action_just_pressed("lane_right"):
		lanes.try_step(1)
	time_rewind.set_stutter_held(Input.is_action_pressed("stutter"))
	if Input.is_action_just_pressed("rewind"):
		time_rewind.try_rewind()
	if Input.is_action_just_pressed("weapon_1"):
		combat.set_weapon("sword")
	if Input.is_action_just_pressed("weapon_2"):
		combat.set_weapon("bow")
	if Input.is_action_just_pressed("weapon_3"):
		combat.set_weapon("crossbow")

	move_and_slide()
	_update_ghost()


func _update_ghost() -> void:
	if lanes.showing_ghost():
		var gp: Vector3 = global_position
		gp.z = lanes.ghost_z()
		var gs: Vector3 = Vector3.ONE * float(lanes.FAR_SCALE)
		visuals.show_ghost_at(gp, gs)
	elif time_rewind.showing_afterimages():
		var xf: Transform3D = time_rewind.afterimage_xform()
		visuals.show_ghost_at(xf.origin, scale)
	else:
		visuals.hide_ghost()


func _on_died() -> void:
	var flow = get_node_or_null("/root/GameFlow")
	if flow:
		flow.notify_player_died()
