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
# Crowds: only the people near the camera get the full articulated body (built lazily); everyone else is a cheap crowd figure drawn
# with two MultiMeshes, so hundreds of people cost a handful of draw calls. Distant animals are not animated, very distant ones hidden.
const NEAR_ENTER := 30.0          # a person closer than this to the camera gets the full body ...
const NEAR_EXIT := 36.0           # ... and keeps it until farther than this (stops flicker at the edge)
const MAX_FULL_PEOPLE := 60       # never more than this many full bodies at once, whatever the camera sees
const SELECTED_FULL_RANGE := 90.0
const ANIMATE_ANIMALS_WITHIN := 55.0
const HIDE_ANIMALS_BEYOND := 150.0
const LOD_INTERVAL := 0.25
var crowd_body := MultiMeshInstance3D.new()
var crowd_head := MultiMeshInstance3D.new()
var _crowd_capacity := 0
var crowd_flags := PackedByteArray()       # per person, in drawing order: 1 = drawn as a crowd figure (tests read this, not the renderer)
var _lod_clock := 99.0
var full_people_count := 0
# Speech bubbles: what inhabitants recently SAID (public speech from /api/v1/live `speech`), drawn above their heads. A recorded
# reflection is offered only as a text-less "..." thought bubble: reflections are private and their text is never published.
const MAX_BUBBLES := 14
const BUBBLE_RANGE := 70.0
const BUBBLE_MAX_CHARS := 90
const BUBBLE_CHARS_PER_LINE := 22.0
const BUBBLE_FONT := 32
const BUBBLE_PIXEL := 0.0075
const BUBBLE_WIDTH_PX := 400.0
var bubbles_on := true
var bubble_seconds_override := -1.0        # tests only
var _speech := {}                          # agent id -> {text, kind, until}
var _seen_speech := {}                     # "agent:tick:kind" -> tick (so a poll that repeats a line does not restart its bubble)
var _bubble_pool: Array = []
var human_mode := "procedural"    # "procedural": every person is built from their recorded age (grows); "models": rigged adults when fetched

func _ready() -> void:
	var tm := TorusMesh.new(); tm.inner_radius = 0.7; tm.outer_radius = 0.9
	ring.mesh = tm; ring.material_override = _mat("#e5bf64", true); ring.visible = false
	add_child(ring)
	trees.multimesh = _multimesh(_cone(0.5, 2.4)); small.multimesh = _multimesh(_sphere(0.2))
	add_child(trees); add_child(small)
	# Crowd figure for a person of unit height: a capsule body and a sphere head, scaled per person.
	var cap := CapsuleMesh.new(); cap.radius = 0.11; cap.height = 0.66; cap.radial_segments = 8; cap.rings = 3
	var head := SphereMesh.new(); head.radius = 0.075; head.height = 0.15; head.radial_segments = 8; head.rings = 4
	crowd_body.multimesh = _multimesh(cap); crowd_head.multimesh = _multimesh(head)
	var vc := StandardMaterial3D.new(); vc.vertex_color_use_as_albedo = true; vc.roughness = 0.9
	crowd_body.material_override = vc; crowd_head.material_override = vc
	add_child(crowd_body); add_child(crowd_head)
	for i in MAX_BUBBLES:
		var bubble := _make_bubble(); add_child(bubble); _bubble_pool.append(bubble)

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
	h.setup(a, false)          # a crowd figure until the camera comes close (see _update_lod)
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
	_refresh_crowd_colors()
	_take_speech(live)
	_lod_clock = 99.0                  # re-decide who is near right away after a poll

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

func _make_bubble() -> Node3D:
	var root := Node3D.new(); root.visible = false
	var bg := MeshInstance3D.new(); bg.name = "bg"; bg.mesh = QuadMesh.new()
	var m := StandardMaterial3D.new()
	m.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED; m.billboard_mode = BaseMaterial3D.BILLBOARD_ENABLED
	m.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA; m.no_depth_test = true; m.render_priority = 1; m.albedo_color = Color(1, 1, 1, 0.92)
	bg.material_override = m; root.add_child(bg)
	var label := Label3D.new(); label.name = "label"
	label.billboard = BaseMaterial3D.BILLBOARD_ENABLED; label.font_size = BUBBLE_FONT; label.pixel_size = BUBBLE_PIXEL; label.outline_size = 0
	label.modulate = Color("#1b1b1b"); label.width = BUBBLE_WIDTH_PX; label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	label.no_depth_test = true; label.render_priority = 2
	root.add_child(label)
	return root

func _take_speech(live: Dictionary) -> void:
	var now := Time.get_ticks_msec() / 1000.0
	for item in live.get("speech", []):
		var key := "%s:%d:%s" % [str(item.get("agent_id")), int(item.get("tick", 0)), str(item.get("kind"))]
		if _seen_speech.has(key):
			continue
		_seen_speech[key] = int(item.get("tick", 0))
		var kind := str(item.get("kind", "speech"))
		var text := ""
		var seconds := 3.0
		if kind == "thought":
			text = "\u2026"                       # a thought is shown, never its content
		else:
			text = str(item.get("text", ""))
			if text.length() > BUBBLE_MAX_CHARS:
				text = text.substr(0, BUBBLE_MAX_CHARS - 1) + "\u2026"
			seconds = clampf(2.5 + 0.06 * text.length(), 4.0, 11.0)
		if bubble_seconds_override > 0.0:
			seconds = bubble_seconds_override
		_speech[str(item.get("agent_id"))] = {"text": text, "kind": kind, "until": now + seconds}
	if _seen_speech.size() > 1500:                 # forget old keys
		for key in _seen_speech.keys():
			if int(_seen_speech[key]) < current_tick - 200:
				_seen_speech.erase(key)

## Currently visible bubbles, for tests and the HUD: [{id, text, kind}].
func bubbles_shown() -> Array:
	var out := []
	for b: Node3D in _bubble_pool:
		if b.visible:
			out.append({"id": str(b.get_meta("agent")), "text": str(b.get_meta("text")), "kind": str(b.get_meta("kind"))})
	return out

func _update_bubbles() -> void:
	var now := Time.get_ticks_msec() / 1000.0
	for id in _speech.keys():
		if float(_speech[id].until) < now:
			_speech.erase(id)
	var active := []
	var cam := get_viewport().get_camera_3d()
	if bubbles_on:
		for id in _speech:
			if not people.has(id):
				continue
			var d := 0.0 if cam == null else float(people[id].global_position.distance_to(cam.global_position))
			if d <= BUBBLE_RANGE:
				active.append([d, id])
		active.sort_custom(func(a, b): return a[0] < b[0])
	for i in MAX_BUBBLES:
		var bubble: Node3D = _bubble_pool[i]
		if i >= active.size():
			bubble.visible = false
			continue
		var id: String = active[i][1]
		var sp: Dictionary = _speech[id]
		var person: Node3D = people[id]
		if str(bubble.get_meta("agent", "")) != id or str(bubble.get_meta("text", "")) != str(sp.text):
			bubble.set_meta("agent", id); bubble.set_meta("text", str(sp.text)); bubble.set_meta("kind", str(sp.kind))
			var label: Label3D = bubble.get_node("label"); label.text = str(sp.text)
			var chars := float(maxi(str(sp.text).length(), 1))
			var lines := ceilf(chars / BUBBLE_CHARS_PER_LINE)
			var w := minf(chars, BUBBLE_CHARS_PER_LINE) * (BUBBLE_FONT * 0.55 * BUBBLE_PIXEL) + 0.3
			var h := lines * (BUBBLE_FONT * 1.3 * BUBBLE_PIXEL) + 0.2
			bubble.get_node("bg").mesh.size = Vector2(w, h)
			bubble.set_meta("half_height", h * 0.5)
			bubble.get_node("bg").material_override.albedo_color = Color(0.86, 0.91, 1.0, 0.92) if str(sp.kind) == "thought" else Color(1, 1, 1, 0.92)
		var top: float = person.top_y() if person.has_method("top_y") else 2.7
		var half: float = float(bubble.get_meta("half_height", 0.4))
		var pos := person.position + Vector3(0.0, top + 0.35 + half, 0.0)
		for j in i:                                                # nearer speakers keep their place; neighbours' bubbles stack upward
			var other: Node3D = _bubble_pool[j]
			if other.visible and absf(other.position.x - pos.x) < 2.2 and absf(other.position.z - pos.z) < 2.2 \
					and absf(other.position.y - pos.y) < half + float(other.get_meta("half_height", 0.4)) + 0.05:
				pos.y = other.position.y + float(other.get_meta("half_height", 0.4)) + half + 0.1
		bubble.position = pos
		bubble.visible = true

func _is_full(n: Node3D) -> bool:
	return (not n.has_method("set_detail")) or bool(n.detail)       # rigged model nodes are always drawn in full

func _update_lod() -> void:
	var cam := get_viewport().get_camera_3d()
	if cam == null:
		return
	var cp: Vector3 = cam.global_position
	var near := []
	for id in people:
		var n: Node3D = people[id]
		if not n.has_method("set_detail"):
			continue
		var d: float = n.global_position.distance_to(cp)
		var limit := NEAR_EXIT if bool(n.detail) else NEAR_ENTER
		if id == selected and d <= SELECTED_FULL_RANGE:
			limit = SELECTED_FULL_RANGE
		if d <= limit:
			near.append([d - (1000.0 if id == selected else 0.0), n])
	near.sort_custom(func(a, b): return a[0] < b[0])
	var keep := {}
	for i in mini(near.size(), MAX_FULL_PEOPLE):
		keep[near[i][1]] = true
	full_people_count = 0
	for id in people:
		var n: Node3D = people[id]
		if not n.has_method("set_detail"):
			full_people_count += 1
			continue
		var want: bool = keep.has(n)
		if want != bool(n.detail):
			n.set_detail(want)
		if want:
			full_people_count += 1
	for n: Node3D in animals.values():
		var d: float = n.global_position.distance_to(cp)
		n.visible = d <= HIDE_ANIMALS_BEYOND
		n.set_meta("animate", d <= ANIMATE_ANIMALS_WITHIN)

func _ensure_crowd_capacity() -> void:
	var need := maxi(people.size(), 1)
	if need <= _crowd_capacity:
		return
	_crowd_capacity = maxi(64, int(pow(2.0, ceil(log(float(need)) / log(2.0)))))
	crowd_body.multimesh.instance_count = _crowd_capacity
	crowd_head.multimesh.instance_count = _crowd_capacity
	crowd_flags.resize(_crowd_capacity)
	for i in _crowd_capacity:                                      # unused instances stay invisible
		crowd_body.multimesh.set_instance_transform(i, Transform3D(Basis.from_scale(Vector3.ZERO), Vector3.ZERO))
		crowd_head.multimesh.set_instance_transform(i, Transform3D(Basis.from_scale(Vector3.ZERO), Vector3.ZERO))

func _refresh_crowd_colors() -> void:
	_ensure_crowd_capacity()
	var i := 0
	for id in people:
		var n: Node3D = people[id]
		if n.has_method("set_detail"):
			crowd_body.multimesh.set_instance_color(i, n.cloth_color)
			crowd_head.multimesh.set_instance_color(i, n.skin_color)
		i += 1

func _update_crowd() -> void:
	var mb := crowd_body.multimesh
	var mh := crowd_head.multimesh
	var i := 0
	var hidden := Transform3D(Basis.from_scale(Vector3.ZERO), Vector3.ZERO)
	for id in people:
		var n: Node3D = people[id]
		if n.has_method("set_detail") and not bool(n.detail):
			var s: float = n.height_units
			var b := Basis.from_euler(Vector3(0.0, n.rotation.y, 0.0)).scaled(Vector3(s, s, s))
			mb.set_instance_transform(i, Transform3D(b, n.position + Vector3(0.0, 0.43 * s, 0.0)))
			mh.set_instance_transform(i, Transform3D(b, n.position + Vector3(0.0, 0.9 * s, 0.0)))
			crowd_flags[i] = 1
		else:
			mb.set_instance_transform(i, hidden)
			mh.set_instance_transform(i, hidden)
			crowd_flags[i] = 0
		i += 1

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
	_lod_clock += delta
	if _lod_clock >= LOD_INTERVAL:
		_lod_clock = 0.0
		_update_lod()
	for n: Node3D in animals.values():   # poses follow the recorded action and real movement (animal_motion.gd); only nearby ones
		if not n.get_meta("animate", true):
			continue
		var moving_a: bool = n.has_meta("target") and n.position.distance_to(n.get_meta("target")) > 0.06
		animal_builder.apply_pose(n, AnimalMotion.pose(str(n.get_meta("group", "mammal")), str(n.get_meta("action", "")),
			moving_a, clock + float(n.get_meta("phase", 0.0))))
	for n in people.values():       # animation follows what the simulation recorded (see animation_map.gd); only full bodies
		if n.has_method("play_state") and _is_full(n):
			var moving: bool = n.has_meta("target") and n.position.distance_to(n.get_meta("target")) > 0.06
			n.play_state(AnimationMap.state_for(n.get_meta("last_action", {}), current_tick, moving))
	_update_crowd()
	_update_bubbles()
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
