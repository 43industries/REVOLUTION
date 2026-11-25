extends Node
class_name Combat
## Sword combat: wind-up / active / recovery, one hit per swing.

signal dealt_damage(target: Node, amount: float, move_id: String)
signal died

enum Phase { NONE, WINDUP, ACTIVE, RECOVERY }

var db
var weapon: String = "sword"
var max_hp: float = 100.0
var hp: float = 100.0
var facing: int = 1
var kills: int = 0
var hurt_flash: float = 0.0
var blocking: bool = false
var can_block: bool = true
var can_dodge: bool = true
var can_parry: bool = true

var phase: Phase = Phase.NONE
var move_id: String = ""
var attack_frame: int = 0
var anim_len: int = 22
var active_lo: int = 9
var active_hi: int = 13
var cooldown: int = 0
var combo_index: int = 0
var combo_window: int = 0
var hit_this_swing: bool = false
var dodge_cd: int = 0
var parry_frames: int = 0

var _host: CharacterBody3D
var _lanes
var _team: String = "player"
var _frame_accum: float = 0.0
var _sword: Node3D


func setup(host: CharacterBody3D, lanes, team: String, sword_node: Node3D = null) -> void:
	_host = host
	_lanes = lanes
	_team = team
	_sword = sword_node
	db = load("res://scripts/weapon_db.gd").new()
	hp = max_hp


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
		if cooldown > 0:
			cooldown -= 1
		if combo_window > 0:
			combo_window -= 1
		if dodge_cd > 0:
			dodge_cd -= 1
		if parry_frames > 0:
			parry_frames -= 1
		if hurt_flash > 0.0:
			hurt_flash = maxf(0.0, hurt_flash - frame * 4.0)
		if phase != Phase.NONE:
			_advance_attack()
		_animate_sword()


func set_weapon(id: String) -> void:
	weapon = id


func try_attack() -> bool:
	if phase != Phase.NONE or cooldown > 0 or blocking:
		return false
	var profile: Dictionary = db.get_profile("sword") if weapon == "sword" else db.get_profile(weapon)
	if profile.is_empty():
		profile = db.get_profile("sword")
	if weapon == "sword":
		if combo_window <= 0:
			combo_index = 0
		var chain: Array = profile.get("combo", ["jab", "slash", "finisher"])
		move_id = String(chain[combo_index % chain.size()])
		combo_index = (combo_index + 1) % chain.size()
		combo_window = int(profile.get("combo_window", 48))
	elif weapon == "bow":
		move_id = "pommel"
	else:
		move_id = "bash"

	var move: Dictionary = db.get_move("sword" if weapon == "sword" else weapon, move_id)
	if move.is_empty() and weapon != "sword":
		move = db.get_move("sword", "jab")
		move_id = "jab"
	anim_len = int(move.get("anim_len", profile.get("anim_len", 22)))
	active_lo = int(move.get("active_lo", profile.get("active_lo", 9)))
	active_hi = int(move.get("active_hi", profile.get("active_hi", 13)))
	cooldown = int(profile.get("cd_max", 36))
	attack_frame = 0
	hit_this_swing = false
	phase = Phase.WINDUP

	var lunge := float(move.get("lunge", 1.0))
	if _host:
		_host.velocity.x += float(facing) * 4.5 * lunge
	return true


func try_block(pressed: bool) -> bool:
	if not can_block or phase != Phase.NONE:
		blocking = false
		return false
	blocking = pressed
	if pressed:
		parry_frames = 12
	return blocking


func try_dodge() -> bool:
	if not can_dodge or dodge_cd > 0 or phase != Phase.NONE:
		return false
	dodge_cd = 45
	if _host:
		_host.velocity.x = float(facing) * -8.0
		_host.velocity.y = 3.0
	return true


func apply_damage(amount: float, attacker_facing: int, from_melee: bool = true) -> float:
	if hp <= 0.0:
		return 0.0
	var final := amount
	if blocking:
		final *= 0.35
	var fx = _fx()
	if parry_frames > 0 and from_melee:
		parry_frames = 0
		if fx:
			fx.hitstop(3)
			fx.shake(8.0, 10)
		return 0.0
	hp = maxf(0.0, hp - final)
	if final > 0.0:
		hurt_flash = 1.0
		if fx:
			fx.hitstop(3 if from_melee else 2)
			fx.shake(5.0 if from_melee else 3.0, 7 if from_melee else 5)
		if _host:
			_host.velocity.x = float(attacker_facing) * 5.0
			_host.velocity.y = 1.5
	if hp <= 0.0:
		died.emit()
	return final


func restore_snapshot(snap: Dictionary) -> void:
	hp = float(snap.get("hp", hp))
	max_hp = float(snap.get("max_hp", max_hp))
	facing = int(snap.get("facing", facing))
	weapon = String(snap.get("weapon", weapon))
	phase = Phase.NONE
	attack_frame = 0
	hit_this_swing = false


func is_attacking() -> bool:
	return phase != Phase.NONE


func _advance_attack() -> void:
	attack_frame += 1
	if attack_frame < active_lo:
		phase = Phase.WINDUP
	elif attack_frame <= active_hi:
		phase = Phase.ACTIVE
		if not hit_this_swing:
			_hit_trace()
	elif attack_frame < anim_len:
		phase = Phase.RECOVERY
	else:
		phase = Phase.NONE
		move_id = ""
		attack_frame = 0


func _hit_trace() -> void:
	if _host == null:
		return
	var move: Dictionary = db.get_move("sword" if weapon == "sword" else weapon, move_id)
	var reach: float = float(move.get("reach", 1.2))
	var space := _host.get_world_3d().direct_space_state
	var from := _host.global_position + Vector3(0, 1.0, 0)
	var to := from + Vector3(float(facing) * reach, 0, 0)
	var q := PhysicsRayQueryParameters3D.create(from, to)
	q.collide_with_areas = false
	q.collide_with_bodies = true
	q.exclude = [_host.get_rid()]
	var hit := space.intersect_ray(q)
	if hit.is_empty():
		# Broad overlap fallback
		_overlap_hit(move, reach)
		return
	var collider = hit.get("collider")
	_try_damage_target(collider, move)


func _overlap_hit(move: Dictionary, reach: float) -> void:
	var sphere := SphereShape3D.new()
	sphere.radius = reach * 0.55
	var params := PhysicsShapeQueryParameters3D.new()
	params.shape = sphere
	params.transform = Transform3D(Basis.IDENTITY, _host.global_position + Vector3(float(facing) * reach * 0.5, 1.0, 0))
	params.exclude = [_host.get_rid()]
	var hits := _host.get_world_3d().direct_space_state.intersect_shape(params, 8)
	for h in hits:
		if _try_damage_target(h.get("collider"), move):
			return


func _try_damage_target(collider: Object, move: Dictionary) -> bool:
	if collider == null or collider == _host:
		return false
	var other_combat = null
	if collider is Node:
		other_combat = (collider as Node).get_node_or_null("Combat")
		if other_combat == null and (collider as Node).get_parent():
			other_combat = (collider as Node).get_parent().get_node_or_null("Combat")
		if other_combat == null:
			for c in (collider as Node).get_children():
				if c.get_script() and String(c.get_script().resource_path).ends_with("combat.gd"):
					other_combat = c
					break
	if other_combat == null or other_combat == self:
		return false
	if other_combat._team == _team:
		return false
	if _lanes and other_combat._lanes:
		if not _lanes.can_hit(other_combat._lanes.lane_index):
			return false
	var dmg := randf_range(float(move.get("dmg_min", 16)), float(move.get("dmg_max", 24)))
	var applied: float = other_combat.apply_damage(dmg, facing, true)
	if applied > 0.0:
		hit_this_swing = true
		dealt_damage.emit(other_combat, applied, move_id)
		var hfx = _fx()
		if hfx:
			hfx.hitstop(int(move.get("freeze", 3)))
			hfx.shake(float(move.get("shake_mag", 7)), int(move.get("shake_frames", 9)))
		if other_combat.hp <= 0.0:
			kills += 1
		return true
	return false


func _animate_sword() -> void:
	if _sword == null:
		return
	var t := 0.0
	if phase == Phase.WINDUP:
		t = float(attack_frame) / maxf(1.0, float(active_lo))
		_sword.rotation_degrees = Vector3(0, 0, lerpf(20.0, -10.0, t) * float(facing))
	elif phase == Phase.ACTIVE:
		t = float(attack_frame - active_lo) / maxf(1.0, float(active_hi - active_lo))
		_sword.rotation_degrees = Vector3(0, 0, lerpf(-10.0, -110.0, t) * float(facing))
	elif phase == Phase.RECOVERY:
		t = float(attack_frame - active_hi) / maxf(1.0, float(anim_len - active_hi))
		_sword.rotation_degrees = Vector3(0, 0, lerpf(-110.0, 20.0, t) * float(facing))
	else:
		_sword.rotation_degrees = Vector3(0, 0, 20.0 * float(facing))
