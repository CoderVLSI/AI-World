extends RefCounted
## Builds a low-poly animal from primitives, one silhouette per species. Purely presentational: size, shape and
## colour are display choices (colour comes from the simulation's species record). Animals whose real size would be
## invisible at world scale (insects) are drawn larger, listed in `boost`. The body faces +Z like the people do.

const AnimalMotion := preload("res://animal_motion.gd")
const METRE := 1.6     # display units per metre, same as the animated people (MODEL_VISUAL_SCALE)

# Metres. quad: body w/h/l, leg length, neck, head radius, snout, ear length, tail length.
const SPECS := {
	"deer":   {"kind": "quad", "w": 0.38, "h": 0.5, "l": 1.2, "leg": 0.7, "neck": 0.4, "head": 0.12, "snout": 0.2, "ear": 0.14, "tail": 0.12, "antlers": true},
	"rabbit": {"kind": "quad", "w": 0.18, "h": 0.2, "l": 0.38, "leg": 0.1, "neck": 0.05, "head": 0.07, "snout": 0.06, "ear": 0.22, "tail": 0.06, "boost": 1.4},
	"boar":   {"kind": "quad", "w": 0.45, "h": 0.45, "l": 1.0, "leg": 0.3, "neck": 0.15, "head": 0.16, "snout": 0.25, "ear": 0.1, "tail": 0.14},
	"wolf":   {"kind": "quad", "w": 0.28, "h": 0.38, "l": 0.95, "leg": 0.5, "neck": 0.25, "head": 0.12, "snout": 0.25, "ear": 0.12, "tail": 0.45},
	"fox":    {"kind": "quad", "w": 0.2, "h": 0.28, "l": 0.65, "leg": 0.3, "neck": 0.15, "head": 0.1, "snout": 0.18, "ear": 0.13, "tail": 0.5, "boost": 1.2},
	"sparrow": {"kind": "bird", "w": 0.1, "h": 0.1, "l": 0.16, "beak": 0.04, "span": 0.24, "boost": 2.2},
	"crow":   {"kind": "bird", "w": 0.16, "h": 0.16, "l": 0.42, "beak": 0.09, "span": 0.9, "boost": 1.3},
	"duck":   {"kind": "bird", "w": 0.2, "h": 0.2, "l": 0.5, "beak": 0.1, "span": 0.8},
	"owl":    {"kind": "bird", "w": 0.2, "h": 0.28, "l": 0.34, "beak": 0.05, "span": 0.9},
	"carp":   {"kind": "fish", "w": 0.14, "h": 0.2, "l": 0.6},
	"butterfly": {"kind": "insect", "w": 0.02, "h": 0.02, "l": 0.05, "span": 0.07, "boost": 4.5, "wings": true},
	"bee":    {"kind": "insect", "w": 0.02, "h": 0.02, "l": 0.05, "span": 0.025, "boost": 6.0, "stripes": true},
}
const FALLBACK_BY_GROUP := {
	"mammal": {"kind": "quad", "w": 0.3, "h": 0.4, "l": 0.8, "leg": 0.4, "neck": 0.2, "head": 0.11, "snout": 0.15, "ear": 0.1, "tail": 0.2},
	"bird": {"kind": "bird", "w": 0.14, "h": 0.14, "l": 0.3, "beak": 0.06, "span": 0.5},
	"fish": {"kind": "fish", "w": 0.12, "h": 0.16, "l": 0.5},
	"insect": {"kind": "insect", "w": 0.02, "h": 0.02, "l": 0.05, "span": 0.04, "boost": 5.0},
}

var _materials := {}

func _mat(c: Color) -> StandardMaterial3D:
	var key := c.to_html()
	if not _materials.has(key):
		var m := StandardMaterial3D.new(); m.albedo_color = c; m.roughness = 0.9
		_materials[key] = m
	return _materials[key]

func _ellipsoid(parent: Node3D, size: Vector3, pos: Vector3, c: Color) -> MeshInstance3D:
	var mi := MeshInstance3D.new(); var sm := SphereMesh.new()
	sm.radius = 0.5; sm.height = 1.0; sm.radial_segments = 10; sm.rings = 5
	mi.mesh = sm; mi.scale = size * METRE; mi.position = pos * METRE; mi.material_override = _mat(c)
	parent.add_child(mi)
	return mi

func _box(parent: Node3D, size: Vector3, pos: Vector3, c: Color) -> MeshInstance3D:
	var mi := MeshInstance3D.new(); var bm := BoxMesh.new()
	bm.size = size * METRE; mi.mesh = bm; mi.position = pos * METRE; mi.material_override = _mat(c)
	parent.add_child(mi)
	return mi

func _cyl(parent: Node3D, radius: float, length: float, pos: Vector3, c: Color) -> MeshInstance3D:
	var mi := MeshInstance3D.new(); var cm := CylinderMesh.new()
	cm.top_radius = radius * METRE; cm.bottom_radius = radius * METRE * 0.8; cm.height = length * METRE
	cm.radial_segments = 6; mi.mesh = cm; mi.position = pos * METRE; mi.material_override = _mat(c)
	parent.add_child(mi)
	return mi

func _pivot(parent: Node3D, pos: Vector3) -> Node3D:
	var n := Node3D.new(); n.position = pos * METRE
	parent.add_child(n)
	return n

func spec_for(species_key: String, group: String) -> Dictionary:
	if SPECS.has(species_key):
		return SPECS[species_key]
	return FALLBACK_BY_GROUP.get(group, FALLBACK_BY_GROUP["mammal"])

## Returns a Node3D whose meta "parts" holds the movable pieces for apply_pose().
func build(species_key: String, group: String, color_hex: String, sex: String = "") -> Node3D:
	var spec: Dictionary = spec_for(species_key, group)
	var c := Color(color_hex)
	var dark := c.darkened(0.35)
	var root := Node3D.new()
	var rig := Node3D.new(); root.add_child(rig)
	var parts := {"rig": rig, "legs": [], "kind": str(spec.kind), "leg_len": 0.0}
	match str(spec.kind):
		"quad": _build_quad(rig, parts, spec, c, dark, sex)
		"bird": _build_bird(rig, parts, spec, c, dark)
		"fish": _build_fish(rig, parts, spec, c, dark)
		_: _build_insect(rig, parts, spec, c, dark)
	root.scale = Vector3.ONE * float(spec.get("boost", 1.0))
	root.set_meta("parts", parts)
	return root

func _build_quad(rig: Node3D, parts: Dictionary, s: Dictionary, c: Color, dark: Color, sex: String) -> void:
	var leg := float(s.leg); var w := float(s.w); var h := float(s.h); var l := float(s.l)
	var body := _ellipsoid(rig, Vector3(w, h, l), Vector3(0, leg + h * 0.4, 0), c)
	parts["body"] = body
	for corner in [Vector2(1, 1), Vector2(-1, 1), Vector2(1, -1), Vector2(-1, -1)]:   # FL FR BL BR (x, z sign)
		var pv := _pivot(rig, Vector3(corner.x * w * 0.3, leg, corner.y * l * 0.32))
		_cyl(pv, 0.035, leg, Vector3(0, -leg * 0.5, 0), dark)
		parts["legs"].append(pv)
	parts["leg_len"] = leg
	var head := _pivot(rig, Vector3(0, leg + h * 0.65, l * 0.42))
	_cyl(head, 0.05, float(s.neck), Vector3(0, float(s.neck) * 0.25, float(s.neck) * 0.3), c).rotation.x = 0.9
	var hz := float(s.neck) * 0.55
	_ellipsoid(head, Vector3(1, 1, 1.2) * float(s.head) * 2.0, Vector3(0, float(s.neck) * 0.55, hz), c)
	_ellipsoid(head, Vector3(0.55, 0.5, 1.0) * float(s.snout) * 1.4, Vector3(0, float(s.neck) * 0.5, hz + float(s.head) + float(s.snout) * 0.3), dark)
	for side in [-1.0, 1.0]:
		var ear := _cyl(head, 0.025, float(s.ear), Vector3(side * float(s.head) * 0.7, float(s.neck) * 0.55 + float(s.head) + float(s.ear) * 0.4, hz - 0.02), dark)
		ear.rotation.z = -side * 0.2
		if bool(s.get("antlers", false)) and sex == "male":
			var a := _cyl(head, 0.015, 0.3, Vector3(side * float(s.head) * 0.6, float(s.neck) * 0.55 + float(s.head) + 0.18, hz - 0.04), dark)
			a.rotation.z = -side * 0.5
	parts["head"] = head
	var tail := _pivot(rig, Vector3(0, leg + h * 0.6, -l * 0.5))
	var tl := float(s.tail)
	_ellipsoid(tail, Vector3(0.08, 0.08, tl) * 1.0, Vector3(0, 0, -tl * 0.4), c if tl < 0.3 else c.lightened(0.15))
	parts["tail"] = tail

func _build_bird(rig: Node3D, parts: Dictionary, s: Dictionary, c: Color, dark: Color) -> void:
	var w := float(s.w); var h := float(s.h); var l := float(s.l)
	var legs := 0.07 + h * 0.4
	parts["leg_len"] = legs
	_ellipsoid(rig, Vector3(w, h, l), Vector3(0, legs + h * 0.5, 0), c)
	for side in [-1.0, 1.0]:
		var pv := _pivot(rig, Vector3(side * w * 0.25, legs, 0))
		_cyl(pv, 0.012, legs, Vector3(0, -legs * 0.5, 0), dark)
		parts["legs"].append(pv)
	var head := _pivot(rig, Vector3(0, legs + h * 0.8, l * 0.38))
	_ellipsoid(head, Vector3(1, 1, 1) * w * 0.75, Vector3(0, w * 0.1, w * 0.2), c)
	var beak := _box(head, Vector3(0.025, 0.02, float(s.beak)), Vector3(0, w * 0.05, w * 0.55 + float(s.beak) * 0.4), Color("#e0a63c"))
	beak.rotation.x = 0.0
	parts["head"] = head
	for side in [-1.0, 1.0]:
		var wing := _pivot(rig, Vector3(side * w * 0.45, legs + h * 0.75, 0))
		_box(wing, Vector3(float(s.span) * 0.5, 0.015, l * 0.7), Vector3(side * float(s.span) * 0.25, 0, 0), c.darkened(0.15))
		parts["wing_r" if side > 0 else "wing_l"] = wing
	var tail := _pivot(rig, Vector3(0, legs + h * 0.5, -l * 0.45))
	_box(tail, Vector3(w * 0.7, 0.012, l * 0.4), Vector3(0, 0, -l * 0.18), dark)
	parts["tail"] = tail

func _build_fish(rig: Node3D, parts: Dictionary, s: Dictionary, c: Color, dark: Color) -> void:
	var w := float(s.w); var h := float(s.h); var l := float(s.l)
	var body := _ellipsoid(rig, Vector3(w, h, l), Vector3(0, 0, 0), c)
	parts["body"] = body
	_box(rig, Vector3(0.015, h * 0.5, l * 0.25), Vector3(0, h * 0.55, -l * 0.05), dark)
	var tail := _pivot(rig, Vector3(0, 0, -l * 0.45))
	_box(tail, Vector3(0.015, h * 0.9, l * 0.28), Vector3(0, 0, -l * 0.12), dark)
	parts["tail"] = tail
	_ellipsoid(rig, Vector3(0.03, 0.03, 0.03), Vector3(w * 0.4, h * 0.1, l * 0.32), Color("#202428"))
	_ellipsoid(rig, Vector3(0.03, 0.03, 0.03), Vector3(-w * 0.4, h * 0.1, l * 0.32), Color("#202428"))

func _build_insect(rig: Node3D, parts: Dictionary, s: Dictionary, c: Color, dark: Color) -> void:
	var l := float(s.l)
	_ellipsoid(rig, Vector3(0.022, 0.022, l), Vector3(0, 0, 0), dark if bool(s.get("wings", false)) else Color("#e0cc78"))
	if bool(s.get("stripes", false)):
		_ellipsoid(rig, Vector3(0.024, 0.024, 0.02), Vector3(0, 0, -l * 0.25), Color("#2b2620"))
	var span := float(s.span)
	for side in [-1.0, 1.0]:
		var wing := _pivot(rig, Vector3(side * 0.01, 0.01, 0))
		var wc := c if bool(s.get("wings", false)) else Color(1, 1, 1, 1).lerp(c, 0.2)
		_box(wing, Vector3(span, 0.004, span * 0.8), Vector3(side * span * 0.5, 0, 0), wc)
		parts["wing_r" if side > 0 else "wing_l"] = wing

## Apply a pose from AnimalMotion.pose(). hover/drop are in metres.
func apply_pose(root: Node3D, pose: Dictionary) -> void:
	var parts: Dictionary = root.get_meta("parts", {})
	if parts.is_empty():
		return
	var rig: Node3D = parts.rig
	rig.position.y = (float(pose.hover) + float(pose.bob) - float(pose.drop) * float(parts.leg_len)) * METRE
	rig.rotation.x = float(pose.body_pitch)
	rig.rotation.y = float(pose.sway)
	var legs: Array = parts.legs
	for i in legs.size():
		var swing := float(pose.leg) * (1.0 if (i == 0 or i == 3) else -1.0) if legs.size() == 4 else float(pose.leg) * (1.0 if i == 0 else -1.0)
		legs[i].rotation.x = swing
	if parts.has("head"):
		parts.head.rotation.x = float(pose.head_pitch)
	if parts.has("tail"):
		parts.tail.rotation.y = float(pose.tail_yaw)
	if parts.has("wing_l"):
		parts.wing_l.rotation.z = float(pose.wing)
		parts.wing_r.rotation.z = -float(pose.wing)
