extends SceneTree
## Run: godot --headless --path godot --script res://tests/crowd_test.gd
## Level of detail for crowds: full bodies only near the camera, crowd figures (MultiMesh) for everyone else.
const Actors := preload("res://actors.gd")
const Human := preload("res://human.gd")
var failures := 0

class StubTerrain extends RefCounted:
	const HEIGHT_SCALE := 1.0
	func height_at(_x: float, _z: float) -> float:
		return 0.0

func check(cond: bool, what: String) -> void:
	if not cond:
		failures += 1; print("FAIL: ", what)

func _count(n: Node) -> int:
	var c := 1
	for k in n.get_children():
		c += _count(k)
	return c

func _initialize() -> void:
	# A person who is only a crowd figure builds nothing, remembers growth, and gets a body the first time it is shown.
	var h: Node3D = Human.new()
	h.setup({"id": "agent-0001", "gender": "woman", "age_years": 4.0, "height_cm": 100.0, "skin_tone": "#8d5c40", "clothing_color": "#8e709d"}, false)
	check(not h.built and not h.detail and h.get_child_count() == 0, "a crowd figure has no rig")
	check(absf(float(h.top_y()) - 1.0 * Human.METRE) < 1e-6, "its height is known without a rig")
	h.set_growth(10.0, 140.0)
	check(not h.built and absf(float(h.top_y()) - 1.4 * Human.METRE) < 1e-6, "growth is remembered while it is a crowd figure")
	h.set_detail(true)
	check(h.built and h.detail and absf(float(h.lens.height) - 1.4 * Human.METRE) < 1e-6, "the rig is built at the remembered size when shown")
	var kids := h.get_child_count()
	h.set_detail(false); h.set_detail(true)
	check(h.get_child_count() == kids, "showing and hiding again does not rebuild")
	check(not h.parts.rig.visible == false, "shown again")
	h.set_detail(false)
	check(not h.parts.rig.visible and not h.detail, "hidden when far")
	h.free()
	# Bodies share meshes and materials: two people of the same colours use the same material objects.
	var a: Node3D = Human.new(); var b: Node3D = Human.new()
	var look := {"id": "agent-0002", "gender": "man", "age_years": 30.0, "height_cm": 175.0, "skin_tone": "#bd8c68", "clothing_color": "#678b91"}
	a.setup(look); b.setup(look)
	check(a.parts.torso.material_override == b.parts.torso.material_override and a.parts.head.mesh == b.parts.head.mesh, "materials and meshes are shared")
	a.free(); b.free()

	# The crowd in a viewer with a camera.
	var root := Node3D.new(); get_root().add_child(root)
	var cam := Camera3D.new(); root.add_child(cam); cam.current = true
	var actors := Actors.new(); root.add_child(actors)
	var agents := []
	for i in 300:
		agents.append({"id": "agent-%04d" % i, "x": (i * 7) % 120, "z": (i * 13) % 120, "alive": true, "gender": "woman", "age_years": 25.0 + i % 40,
			"height_cm": 170.0, "skin_tone": "#bd8c68", "clothing_color": "#678b91", "last_action": null})
	var animals := []
	for i in 40:
		animals.append({"id": "animal-%06d" % i, "species": "deer", "x": (i * 29) % 128, "z": (i * 31) % 128, "action": "roaming", "sex": "male", "alive": true})
	var live := {"tick": 1, "agents": agents, "resources": [], "objects": [],
		"wildlife": {"species": {"deer": {"name": "Deer", "group": "mammal", "color": "#d6b78a"}}, "animals": animals}}
	await process_frame
	cam.transform = Transform3D(Basis.looking_at(Vector3(0, -1, 0), Vector3.FORWARD), Vector3(500, 400, 500))      # nobody is close
	actors.update_live(live, StubTerrain.new())
	await settle()
	check(actors.full_people_count == 0, "far camera: nobody gets a full body")
	var built := 0
	for n in actors.people.values():
		if n.built: built += 1
	check(built == 0 and _count(actors) < 1500, "far camera: no rigs exist, the scene stays small (%d nodes)" % _count(actors))
	var visible_animals := 0
	for n in actors.animals.values():
		if n.visible: visible_animals += 1
	check(visible_animals == 0, "animals beyond the hide range are hidden")
	# crowd figures are drawn: every person has a non-degenerate instance
	var nonzero := 0
	for i in 300:
		if actors.crowd_flags[i] == 1: nonzero += 1
	check(nonzero == 300, "every person is drawn as a crowd figure")
	# Move the camera into the crowd: full bodies appear, but never more than the cap.
	cam.transform = Transform3D(Basis.looking_at(Vector3(0, -0.5, -1)), Vector3(60, 12, 70))
	await settle()
	check(actors.full_people_count > 0 and actors.full_people_count <= Actors.MAX_FULL_PEOPLE, "near camera: some full bodies, capped (%d)" % actors.full_people_count)
	var full_nodes := 0
	for n in actors.people.values():
		if n.detail:
			full_nodes += 1
			check(n.built and n.parts.rig.visible and n.global_position.distance_to(cam.global_position) <= Actors.NEAR_EXIT + 0.01, "a full body is near and built")
		else:
			check(actors.crowd_flags[list_index(actors, n)] == 1, "a crowd figure is drawn")
	check(full_nodes == actors.full_people_count, "the count matches")
	# a full body is NOT also drawn as a crowd figure
	for id in actors.people:
		var n: Node3D = actors.people[id]
		if n.detail:
			check(actors.crowd_flags[list_index(actors, n)] == 0, "no double drawing")
			break
	# A dense cluster: the cap binds, the rest stay crowd figures.
	for i in 200:
		live.agents[i].x = i % 20; live.agents[i].z = (i / 20) % 20
	actors.update_live(live, StubTerrain.new())
	for id in actors.people:                                       # snap to the targets so the test does not wait for movement
		actors.people[id].position = actors.people[id].get_meta("target")
	cam.transform = Transform3D(Basis.looking_at(Vector3(0, -0.4, -1)), Vector3(10, 10, 32))
	await settle()
	check(actors.full_people_count == Actors.MAX_FULL_PEOPLE, "a dense crowd is capped at %d full bodies (got %d)" % [Actors.MAX_FULL_PEOPLE, actors.full_people_count])
	var crowd_drawn := 0
	for i in actors.people.size():
		if actors.crowd_flags[i] == 1: crowd_drawn += 1
	check(crowd_drawn == actors.people.size() - actors.full_people_count, "everyone not in full is a crowd figure")
	# Walk away again: bodies are hidden (not rebuilt later), so a crowd costs nothing when it is not near.
	cam.transform = Transform3D(Basis.looking_at(Vector3(0, -1, 0), Vector3.FORWARD), Vector3(500, 400, 500))
	await settle()
	check(actors.full_people_count == 0, "moving away hides the bodies again")
	# The selected person gets a body from farther away.
	actors.selected = "agent-0005"
	cam.transform = Transform3D(Basis.looking_at(Vector3(0, -0.5, -1)), Vector3(actors.people["agent-0005"].position.x, 12.0, actors.people["agent-0005"].position.z + 70.0))
	await settle()
	check(actors.people["agent-0005"].detail, "the selected person is shown in full from farther away")
	# Frames run with an unusual poll (a person disappears) and a growth update
	live.agents.remove_at(0)
	live.agents[3].age_years = 5.0; live.agents[3].height_cm = 110.0
	actors.update_live(live, StubTerrain.new())
	await settle()
	check(actors.people.size() == 299, "a person who left is removed")
	print("crowd tests: ", "FAILED" if failures > 0 else "ok")
	quit(1 if failures > 0 else 0)

func settle() -> void:
	await create_timer(0.4).timeout        # the viewer re-decides who is near every 0.25 s
	await process_frame

func list_index(actors, node) -> int:
	var i := 0
	for id in actors.people:
		if actors.people[id] == node:
			return i
		i += 1
	return -1
