extends Node3D
## Turns the /api/v1/live view into 3D figures. Purely presentational: nothing here talks back to the server.

const AnimationMap := preload("res://animation_map.gd")
const CharacterLibrary := preload("res://character_library.gd")
const Human := preload("res://human.gd")
const AnimalBuilder := preload("res://animal_builder.gd")
const AnimalMotion := preload("res://animal_motion.gd")

const PERSON_SCALE := 2.3
const MODEL_VISUAL_SCALE := 1.6   # animated models are drawn a little larger than life so they read at world scale
const RESOURCE_COLORS := {
	"food": "#cbba69", "fruit": "#c46f58", "grain": "#dbc986", "water": "#74bfd1", "wood": "#325a3b",
	"stone": "#959a91", "clay": "#b77c60", "sand": "#c9bb84", "iron_ore": "#8b6554", "copper_ore": "#719a86",
	"coal": "#434340", "salt": "#e7ddd0", "herbs": "#76ad70", "plant_fiber": "#a4b86d", "fish": "#89acbd"}

var terrain
var people := {}      # id -> Node3D
var animals := {}     # id -> Node3D
var things := {}      # id -> Node3D (objects, fires)
var latest_people := {}
var selected := ""
var ring := MeshInstance3D.new()
var trees := MultiMeshInstance3D.new()
var small := MultiMeshInstance3D.new()
var _materials := {}
var library := CharacterLibrary.new()
var animal_builder := AnimalBuilder.new()
var clock := 0.0
var current_tick := 0
var human_mode := "procedural"    # "procedural": every person is built from their recorded age (grows); "models": rigged adults when fetched

func _ready() -> void:
	var tm := TorusMesh.new(); tm.inner_radius = 0.7; tm.outer_radius = 0.9
	ring.mesh = tm; ring.material_override = _mat("#e5bf64", true); ring.visible = false
	add_child(ring)
	trees.multimesh = _multimesh(_cone(0.5, 2.4)); small.multimesh = _multimesh(_sphere(0.2))
	add_child(trees); add_child(small)

func _cone(r: float, h: float) -> Mesh:
	var m := CylinderMesh.new(); m.top_radius = 0.0; m.bottom_radius = r; m.height = h; m.radial_segments = 6; m.rings = 1
	return m

func _sphere(r: float) -> Mesh:
	var m := SphereMesh.new(); m.radius = r; m.height = r * 2.0; m.radial_segments = 8; m.rings = 4
	return m

func _multimesh(mesh: Mesh) -> MultiMesh:
	var mm := MultiMesh.new()
	mm.transform_format = MultiMesh.TRANSFORM_3D; mm.use_colors = true; mm.mesh = mesh
	return mm

func _mat(hex: String, emissive := false) -> StandardMaterial3D:
	var key := hex + ("e" if emissive else "")
	if not _materials.has(key):
		var m := StandardMaterial3D.new(); m.albedo_color = Color(hex); m.roughness = 0.9
		if emissive:
			m.emission_enabled = true; m.emission = Color(hex); m.emission_energy_multiplier = 1.6
		_materials[key] = m
	return _materials[key]

func _ground(x: float, z: float) -> Vector3:
	return Vector3(x, maxf(terrain.height_at(x, z), -0.25 * terrain.HEIGHT_SCALE), z)

func _person_node(a: Dictionary) -> Node3D:
	# Rigged models cannot show a child's proportions (a scaled adult looks like a small adult), so they are opt-in
	# (--humans=models) and used for adults only; everyone else, and everyone by default, grows from their recorded age.
	if human_mode == "models" and library.available and float(a.get("age_years", 25.0)) >= 18.0:
		var body := library.make(a, MODEL_VISUAL_SCALE)
		if body != null:
			return body
	var h := Human.new()
	h.setup(a)
	return h

func _animal_node(b: Dictionary, species: Dictionary) -> Node3D:
	var sp: Dictionary = species.get(str(b.get("species")), {})
	var n := animal_builder.build(str(b.get("species")), str(sp.get("group", "mammal")), str(sp.get("color", "#cccccc")), str(b.get("sex", "")))
	n.set_meta("group", str(sp.get("group", "mammal")))
	n.set_meta("phase", float(hash(str(b.get("id"))) % 628) / 100.0)   # de-synchronise the animals, display only
	return n

func _thing_node(o: Dictionary) -> Node3D:
	var root := Node3D.new(); var mi := MeshInstance3D.new()
	if o.get("kind") == "fire":
		mi.mesh = _cone(0.4, 1.0); mi.position.y = 0.5; mi.material_override = _mat("#ff8a2a", true)
		var light := OmniLight3D.new(); light.omni_range = 9.0; light.light_energy = 1.8; light.light_color = Color("#ffb066")
		light.position.y = 1.0; root.add_child(light)
	else:
		var bm := BoxMesh.new(); bm.size = Vector3(0.7, 0.4, 0.7)
		mi.mesh = bm; mi.position.y = 0.25; mi.material_override = _mat("#b58a5a")
	root.add_child(mi)
	return root

func _sync(nodes: Dictionary, items: Array, make: Callable, place: Callable) -> void:
	var seen := {}
	for it in items:
		var id := str(it.id); seen[id] = true
		if not nodes.has(id):
			var n: Node3D = make.call(it); nodes[id] = n; add_child(n); n.set_meta("fresh", true)
		place.call(nodes[id], it)
	for id in nodes.keys():
		if not seen.has(id):
			nodes[id].queue_free(); nodes.erase(id)

func _place_mover(n: Node3D, x: float, z: float) -> void:
	var t := _ground(x + 0.5, z + 0.5)
	n.set_meta("target", t)
	if n.get_meta("fresh", false):
		n.position = t; n.set_meta("fresh", false)

func update_live(live: Dictionary, terrain_view) -> void:
	terrain = terrain_view
	latest_people.clear()
	var alive := []
	for a in live.get("agents", []):
		latest_people[str(a.id)] = a
		if a.get("alive", false): alive.append(a)
	current_tick = int(live.get("tick", 0))
	_sync(people, alive, _person_node, func(n: Node3D, a: Dictionary):
		var recorded = a.get("last_action")     # note: set_meta(null) would delete the key, so store {} for "none"
		n.set_meta("last_action", recorded if recorded != null else {})
		if n.has_method("set_growth"):
			n.set_growth(float(a.get("age_years", 25.0)), float(a.get("height_cm", 170.0)))
		_place_mover(n, float(a.x), float(a.z)))
	var wl: Dictionary = live.get("wildlife", {})
	var species: Dictionary = wl.get("species", {})
	_sync(animals, wl.get("animals", []), func(b): return _animal_node(b, species),
		func(n: Node3D, b: Dictionary):
			n.set_meta("action", str(b.get("action", "")))     # recorded by the simulation
			_place_mover(n, float(b.x), float(b.z)))
	_sync(things, live.get("objects", []), _thing_node, func(n: Node3D, o: Dictionary):
		n.position = _ground(float(o.x) + 0.5, float(o.z) + 0.5)
		n.visible = o.get("kind") != "fire" or o.get("burning", false))
	_resources(live.get("resources", []))

func _resources(items: Array) -> void:
	var tree_items := []; var small_items := []
	for r in items:
		(tree_items if r.kind == "wood" else small_items).append(r)
	for pair in [[trees.multimesh, tree_items, 1.2], [small.multimesh, small_items, 0.2]]:
		var mm: MultiMesh = pair[0]; var list: Array = pair[1]
		mm.instance_count = list.size()
		for i in list.size():
			var r: Dictionary = list[i]
			var p := _ground(float(r.x) + 0.5, float(r.z) + 0.5)
			mm.set_instance_transform(i, Transform3D(Basis(), p + Vector3(0, pair[2], 0)))
			mm.set_instance_color(i, Color(RESOURCE_COLORS.get(str(r.kind), "#aaaaaa")))

func _process(delta: float) -> void:
	for group in [people, animals]:
		for n: Node3D in group.values():
			if n.has_meta("target"):
				var t: Vector3 = n.get_meta("target")
				if n.position.distance_to(t) > 0.02:
					var dir: Vector3 = t - n.position
					n.position = n.position.lerp(t, clampf(delta * 3.0, 0.0, 1.0))
					if Vector2(dir.x, dir.z).length() > 0.05:
						n.rotation.y = lerp_angle(n.rotation.y, atan2(dir.x, dir.z), clampf(delta * 8.0, 0.0, 1.0))
	clock += delta
	for n: Node3D in animals.values():   # poses follow the recorded action and real movement (animal_motion.gd)
		var moving_a: bool = n.has_meta("target") and n.position.distance_to(n.get_meta("target")) > 0.06
		animal_builder.apply_pose(n, AnimalMotion.pose(str(n.get_meta("group", "mammal")), str(n.get_meta("action", "")),
			moving_a, clock + float(n.get_meta("phase", 0.0))))
	for n in people.values():       # animation follows what the simulation recorded (see animation_map.gd)
		if n.has_method("play_state"):
			var moving: bool = n.has_meta("target") and n.position.distance_to(n.get_meta("target")) > 0.06
			n.play_state(AnimationMap.state_for(n.get_meta("last_action", {}), current_tick, moving))
	if selected != "" and people.has(selected):
		ring.visible = true; ring.position = people[selected].position + Vector3(0, 0.05, 0)
	else:
		ring.visible = false

func pick(camera: Camera3D, screen_pos: Vector2) -> String:
	var best := ""; var best_d := 30.0
	for id in people:
		var top: float = people[id].top_y() * 0.6 if people[id].has_method("top_y") else 1.2
		var p: Vector3 = people[id].position + Vector3(0, top, 0)
		if camera.is_position_behind(p): continue
		var d := camera.unproject_position(p).distance_to(screen_pos)
		if d < best_d: best_d = d; best = id
	return best

func centroid() -> Vector3:
	if people.is_empty(): return Vector3.ZERO
	var s := Vector3.ZERO
	for n in people.values(): s += n.position
	return s / people.size()

func animal_centroid() -> Vector3:
	if animals.is_empty(): return Vector3.ZERO
	var s := Vector3.ZERO
	for n in animals.values(): s += n.position
	return s / animals.size()
