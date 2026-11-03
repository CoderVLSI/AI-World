extends SceneTree
## Run: godot --headless --path godot --script res://tests/animal_test.gd
const Builder := preload("res://animal_builder.gd")
const Motion := preload("res://animal_motion.gd")
var failures := 0

func check(cond: bool, what: String) -> void:
	if not cond:
		failures += 1; print("FAIL: ", what)

func _init() -> void:
	var b := Builder.new()
	var groups := {"deer": "mammal", "rabbit": "mammal", "boar": "mammal", "wolf": "mammal", "fox": "mammal", "sparrow": "bird",
		"crow": "bird", "duck": "bird", "owl": "bird", "carp": "fish", "butterfly": "insect", "bee": "insect"}
	for key in groups:
		var n: Node3D = b.build(key, groups[key], "#aa8844", "male")
		check(n.get_child_count() > 0 and n.has_meta("parts"), key + ": built with movable parts")
		check(b.SPECS.has(key), key + ": has its own silhouette spec")
		# every pose the motion rule can produce applies without error
		for action in Motion.ACTIONS + ["not_an_action"]:
			for moving in [false, true]:
				b.apply_pose(n, Motion.pose(groups[key], action, moving, 1.3))
		n.free()
	# an unknown species still draws (by group), and an empty group falls back to a mammal
	check(b.build("dragon", "bird", "#ffffff").has_meta("parts"), "unknown species falls back to its group")
	check(b.build("dragon", "", "#ffffff").has_meta("parts"), "unknown group falls back to mammal")
	# antlers only for males of a species that has them
	var male: Node3D = b.build("deer", "mammal", "#d6b78a", "male"); var female: Node3D = b.build("deer", "mammal", "#d6b78a", "female")
	check(_count(male) > _count(female), "deer antlers only when the recorded sex is male")
	# poses come only from recorded state
	var idle := Motion.pose("mammal", "roaming", false, 2.0)
	check(idle.leg == 0.0 and idle.drop == 0.0, "standing still: no leg swing, no crouch")
	var walk := Motion.pose("mammal", "roaming", true, 0.2)
	check(absf(walk.leg) > 0.0, "really moving -> legs swing")
	check(Motion.pose("mammal", "resting", false, 1.0).drop > 0.0, "recorded resting -> crouched")
	check(Motion.pose("mammal", "foraging", false, 1.0).head_pitch > 0.5, "foraging -> head to the ground")
	check(Motion.pose("mammal", "hunting", true, 1.0).drop > 0.0, "recorded hunting while moving -> stalking")
	check(Motion.pose("mammal", "roaming", true, 1.0).drop == 0.0, "an animal not recorded as hunting never stalks")
	check(Motion.pose("bird", "flying", true, 1.0).hover > 1.0, "recorded flying -> airborne")
	check(Motion.pose("bird", "roaming", true, 1.0).hover == 0.0, "a bird not recorded as flying stays on the ground")
	check(Motion.pose("bird", "flying", true, 0.05).wing != 0.0, "flying -> wings beat")
	check(Motion.pose("fish", "swimming", true, 0.1).tail_yaw != 0.0, "fish sway their tail")
	check(Motion.pose("mammal", "dancing", false, 1.0).leg == 0.0, "unknown action -> idle")
	check(absf(Motion.pose("mammal", "avoiding predator", true, 0.1).leg) > absf(Motion.pose("mammal", "roaming", true, 0.1).leg), "recorded avoidance -> faster, wider gait")
	check(Motion.pose("mammal", "avoiding predator", false, 1.0).leg == 0.0, "an animal that is not moving does not run")
	print("animal tests: ", "FAILED" if failures > 0 else "ok")
	quit(1 if failures > 0 else 0)

func _count(n: Node) -> int:
	var c := 1
	for k in n.get_children():
		c += _count(k)
	return c
