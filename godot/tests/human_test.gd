extends SceneTree
## Run: godot --headless --path godot --script res://tests/human_test.gd
const Props := preload("res://human_proportions.gd")
const Human := preload("res://human.gd")
var failures := 0

func check(cond: bool, what: String) -> void:
	if not cond:
		failures += 1; print("FAIL: ", what)

func _init() -> void:
	# stage boundaries (mirrors caitanya/lifecycle.py stage(); a Python test cross-checks the numbers)
	for pair in [[0.0, "infant"], [2.99, "infant"], [3.0, "child"], [12.99, "child"], [13.0, "adolescent"], [17.99, "adolescent"],
			[18.0, "adult"], [64.99, "adult"], [65.0, "elder"], [95.0, "elder"]]:
		check(Props.stage_for(pair[0]) == pair[1], "stage at %s is %s" % [pair[0], pair[1]])
	# shape: fractions add up, children have bigger heads and shorter legs than adults, and growth is monotonic
	var prev_head := 1.0
	var prev_leg := 0.0
	for gender in ["woman", "man", "nonbinary", ""]:
		for age in [0.0, 0.5, 1.0, 2.0, 4.0, 6.0, 9.0, 12.0, 15.0, 18.0, 30.0, 50.0, 65.0, 80.0, 95.0, 120.0]:
			var p := Props.proportions(age, gender)
			check(absf(float(p.head) + float(p.leg) + float(p.neck) + float(p.torso) - 1.0) < 1e-6, "parts add up to full height at %s" % age)
			check(float(p.torso) > 0.15 and float(p.torso) < 0.45, "torso fraction is sane at %s" % age)
	for age in range(0, 19):
		var p := Props.proportions(float(age), "woman")
		check(float(p.head) <= prev_head + 1e-9, "head fraction only shrinks while growing (age %d)" % age)
		check(float(p.leg) >= prev_leg - 1e-9, "leg fraction only grows while growing (age %d)" % age)
		prev_head = float(p.head); prev_leg = float(p.leg)
	var baby := Props.proportions(0.0, "")
	var child := Props.proportions(6.0, "")
	var adult := Props.proportions(30.0, "man")
	check(float(baby.head) >= 0.24 and float(adult.head) < 0.14 and float(adult.head) > 0.12, "newborn head ~1/4 of height, adult ~1/7.5")
	check(float(child.head) > float(adult.head) and float(child.leg) < float(adult.leg), "a child is not a small adult")
	check(float(Props.proportions(30.0, "").stoop) == 0.0 and float(Props.proportions(90.0, "").stoop) > 0.1, "only elders stoop")
	check(float(Props.proportions(30.0, "").grey) == 0.0 and float(Props.proportions(80.0, "").grey) == 1.0, "hair greys with age")
	check(float(Props.proportions(30.0, "woman").shoulder) < float(Props.proportions(30.0, "man").shoulder), "display shoulder balance only after puberty")
	check(is_equal_approx(float(Props.proportions(5.0, "woman").shoulder), float(Props.proportions(5.0, "man").shoulder)), "children are not gendered in shape")
	# a built body stands exactly as tall as the simulation says, for every age, and grows IN PLACE
	var agent := {"id": "agent-0007", "gender": "woman", "skin_tone": "#8d5c40", "clothing_color": "#8e709d", "age_years": 0.2, "height_cm": 55.0}
	var h: Node3D = Human.new()
	h.setup(agent)
	var children_before := h.get_child_count()
	var nodes_before := _count(h)
	var prev_ratio := 1.0
	for pair in [[0.2, 55.0], [1.0, 75.0], [4.0, 105.0], [9.0, 135.0], [15.0, 162.0], [30.0, 170.0], [70.0, 168.0], [90.0, 166.0]]:
		h.set_growth(pair[0], pair[1])
		var want: float = float(pair[1]) / 100.0 * Human.METRE
		var top: float = float(h.parts.hips.position.y) + float(h.lens.torso) + float(h.lens.neck) + float(h.lens.head)
		check(absf(top - want) / want < 0.005, "standing height matches the simulation at age %s" % pair[0])
		check(absf(float(h.top_y()) - want) < 1e-6, "top_y reports it")
		if pair[0] <= 30.0:
			var ratio: float = float(h.lens.head) / float(h.lens.height)
			check(ratio <= prev_ratio + 1e-9, "head/height shrinks as the same person grows (age %s)" % pair[0])
			prev_ratio = ratio
	check(h.get_child_count() == children_before and _count(h) == nodes_before, "growth reshapes the same nodes, it does not rebuild")
	var greyed: Color = h.parts.hair.material_override.albedo_color
	check(greyed.r > 0.4, "an elder's hair is grey")
	# nothing in the world makes clothes, so by default a person is drawn bare; the recorded colour is only painted on request
	var skin_hex := Color("#8d5c40")
	check(not Human.show_clothing, "bare by default")
	for part in ["torso", "pelvis", "upper_arm_l", "thigh_l", "shin_r", "foot_l"]:
		check(h.parts[part].material_override.albedo_color.is_equal_approx(skin_hex), part + " is skin when bare")
	check(h.cloth_color.is_equal_approx(skin_hex) and h.skin_color.is_equal_approx(skin_hex), "a crowd figure is bare too")
	Human.show_clothing = true
	var dressed: Node3D = Human.new(); dressed.setup(agent)
	check(dressed.parts["torso"].material_override.albedo_color.is_equal_approx(Color("#8e709d")), "--clothing paints the recorded colour")
	check(not dressed.parts["thigh_l"].material_override.albedo_color.is_equal_approx(skin_hex), "--clothing covers the legs")
	Human.show_clothing = false
	# poses come only from the recorded state
	var idle := Human.targets("idle", 1.0, 0.0, false)
	var walk := Human.targets("walk", 0.3, 0.0, false)
	check(absf(float(idle.hip_l)) < 1e-9 and absf(float(walk.hip_l)) > 0.1, "legs swing only when walking")
	check(float(Human.targets("rest", 0.0, 0.0, false).sit) == 1.0 and float(idle.sit) == 0.0, "rest sits, idle stands")
	check(float(Human.targets("work", 0.0, 0.0, false).torso) > 0.5, "work bends forward")
	check(float(Human.targets("talk", 1.0, 0.0, false).arm_r) < -0.5, "talk raises an arm")
	check(float(Human.targets("eat", 1.0, 0.0, false).elbow_r) < -1.0, "eat brings a hand up")
	check(Human.targets("run", 0.3, 0.0, false).hip_l == idle.hip_l or absf(float(Human.targets("run", 0.3, 0.0, false).hip_l)) < 1e-9, "an unrecorded 'run' state is just idle")
	check(float(Human.targets("idle", 1.0, 0.2, false).torso) > 0.15, "an elder's idle pose keeps the stoop")
	# frames run without error in every state
	for s in ["idle", "walk", "rest", "talk", "work", "eat", "nonsense"]:
		h.play_state(s)
		for i in 5:
			h._process(0.05)
	h.free()
	print("human tests: ", "FAILED" if failures > 0 else "ok")
	quit(1 if failures > 0 else 0)

func _count(n: Node) -> int:
	var c := 1
	for k in n.get_children():
		c += _count(k)
	return c
