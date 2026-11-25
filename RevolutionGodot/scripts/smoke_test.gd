extends SceneTree
## Headless smoke: WeaponDB, WLane math, combat swing numbers.

func _init() -> void:
	var failed := 0
	var db = load("res://scripts/weapon_db.gd").new()
	var jab: Dictionary = db.get_move("sword", "jab")
	if jab.is_empty():
		push_error("WeaponDB missing sword/jab")
		failed += 1
	elif float(jab.get("reach", 0)) <= 0.0:
		push_error("jab reach invalid")
		failed += 1

	var lane = load("res://scripts/w_lane.gd").new()
	lane.lane_index = 2
	if not lane.can_hit(3):
		push_error("lane can_hit adjacent failed")
		failed += 1
	if lane.can_hit(0):
		push_error("lane can_hit far should fail from MID")
		failed += 1

	var move: Dictionary = db.get_move("sword", "slash")
	if int(move.get("freeze", 0)) < 1:
		push_error("slash freeze missing")
		failed += 1

	if failed > 0:
		push_error("smoke_test FAILED (%d)" % failed)
		quit(1)
	else:
		print("smoke_test OK")
		quit(0)
