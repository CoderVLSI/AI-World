extends SceneTree
## Cost of drawing a crowd. Run: godot --headless --path godot --script res://tests/crowd_benchmark.gd -- N_PEOPLE [N_ANIMALS]
## Headless: measures the script work per frame (no GPU). With a window (xvfb-run, --rendering-driver opengl3) it also prints the
## renderer's draw-call and object counts, which do not depend on how fast the GPU is.
const Actors := preload("res://actors.gd")

class StubTerrain extends RefCounted:
	const HEIGHT_SCALE := 1.0
	func height_at(_x: float, _z: float) -> float:
		return 0.0

func _initialize() -> void:
	var args := OS.get_cmdline_user_args()
	var n_people := int(args[0]) if args.size() > 0 else 300
	var n_animals := int(args[1]) if args.size() > 1 else 100
	var close := args.size() > 2 and args[2] == "near"              # camera low over the middle of the crowd (worst case)
	var root := Node3D.new(); get_root().add_child(root)
	var cam := Camera3D.new(); root.add_child(cam)
	cam.transform = Transform3D(Basis.looking_at(Vector3(0, -0.35, -1).normalized() if close else Vector3(0, -0.6, -1).normalized(), Vector3.UP), Vector3(64, 14, 78) if close else Vector3(64, 40, 110)); cam.fov = 55; cam.current = true
	var env := Environment.new(); env.background_mode = Environment.BG_COLOR; env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.ambient_light_color = Color(0.8, 0.8, 0.8)
	var we := WorldEnvironment.new(); we.environment = env; root.add_child(we)
	var sun := DirectionalLight3D.new(); sun.rotation_degrees = Vector3(-50, 20, 0); root.add_child(sun)
	var actors := Actors.new(); root.add_child(actors)
	var rng := RandomNumberGenerator.new(); rng.seed = 7
	var agents := []
	for i in n_people:
		var age := rng.randf_range(1.0, 70.0)
		agents.append({"id": "agent-%04d" % i, "x": rng.randi_range(0, 127), "z": rng.randi_range(0, 127), "alive": true,
			"gender": ["woman", "man", "unspecified"][i % 3], "age_years": age, "height_cm": 60.0 + minf(age, 18.0) / 18.0 * 110.0,
			"skin_tone": "#bd8c68", "clothing_color": ["#678b91", "#b38e5b", "#8e709d", "#758f62"][i % 4], "life_stage": "adult",
			"last_action": {"type": ["move", "rest", "speak", "gather", "eat", "wait"][i % 6], "tick": 1, "origin": "x"}})
	var animals := []
	var kinds := ["deer", "rabbit", "boar", "wolf", "fox", "sparrow", "crow", "duck", "owl", "carp", "butterfly", "bee"]
	var species := {}
	for k in kinds:
		species[k] = {"name": k, "group": "mammal" if kinds.find(k) < 5 else "bird" if kinds.find(k) < 9 else "fish" if k == "carp" else "insect", "color": "#a08060"}
	for i in n_animals:
		animals.append({"id": "animal-%06d" % i, "species": kinds[i % kinds.size()], "x": rng.randi_range(0, 127), "z": rng.randi_range(0, 127),
			"action": ["roaming", "foraging", "resting", "flying"][i % 4], "sex": "male", "alive": true})
	var live := {"tick": 1, "agents": agents, "resources": [], "objects": [], "wildlife": {"species": species, "animals": animals}}
	var stub := StubTerrain.new()
	await process_frame                                            # let the viewer node run its _ready
	var t0 := Time.get_ticks_usec()
	actors.update_live(live, stub)
	var build_ms := (Time.get_ticks_usec() - t0) / 1000.0
	for f in 8:                                                    # let level-of-detail settle
		await process_frame
	var samples := []
	for f in 90:
		# move everyone one step each "poll", like the live view does
		if f % 30 == 0:
			for a in agents:
				a.x = clampi(int(a.x) + rng.randi_range(-1, 1), 0, 127); a.z = clampi(int(a.z) + rng.randi_range(-1, 1), 0, 127)
			live.tick = int(live.tick) + 1
			actors.update_live(live, stub)
		var t := Time.get_ticks_usec()
		await process_frame
		samples.append((Time.get_ticks_usec() - t) / 1000.0)
	samples.sort()
	var avg := 0.0
	for s in samples: avg += s
	avg /= samples.size()
	var nodes := _count(actors)
	var full := int(actors.get("full_people_count")) if actors.get("full_people_count") != null else n_people
	print("FULL_BODIES ", full)
	print("RESULT people=%d animals=%d %s  first build %.0f ms | frame work avg %.2f ms, p95 %.2f ms | scene nodes %d" % [n_people, n_animals, "camera near" if close else "camera far", build_ms, avg, samples[int(samples.size() * 0.95)], nodes])
	if DisplayServer.get_name() != "headless":
		print("RENDER draw_calls=%d objects=%d" % [RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_TOTAL_DRAW_CALLS_IN_FRAME),
			RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_TOTAL_OBJECTS_IN_FRAME)])
	quit()

func _count(n: Node) -> int:
	var c := 1
	for k in n.get_children():
		c += _count(k)
	return c
