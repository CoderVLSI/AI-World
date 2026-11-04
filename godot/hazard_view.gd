extends Node3D
## Draws the lasting hazard zones the witness API publishes (`environment_hazards`): a translucent disc that follows the ground out to the
## zone's radius, a stronger rim, and a plain label. Read-only: it only shows what the simulation already says is there.
## Nothing here is told to the inhabitants; they learn of a zone only through their own observations.

const RINGS := 5
const SEGMENTS := 40
const LIFT := 0.6                   # metres above the ground, so the disc is never z-fighting with it
const COLORS := {
	"wildfire": Color(1.0, 0.36, 0.08), "floodwater": Color(0.16, 0.46, 1.0),
	"heatwave": Color(1.0, 0.84, 0.2), "severe storm": Color(0.62, 0.46, 0.95),
}
const FALLBACK := Color(0.9, 0.9, 0.9)

var zones := {}         # key -> {"node": Node3D, "mat": StandardMaterial3D, "phase": float}
var _time := 0.0

static func word_for(phenomenon: String) -> String:
	return phenomenon         # the API already names the phenomenon in plain words

static func color_for(phenomenon: String) -> Color:
	return COLORS.get(phenomenon, FALLBACK)

static func key_of(h: Dictionary) -> String:
	return "%s:%s:%s:%s" % [str(h.get("phenomenon", "")), str(h.get("x", 0)), str(h.get("z", 0)), str(h.get("start_tick", 0))]

func update_hazards(list: Array, terrain) -> void:
	var live := {}
	for h in list:
		if typeof(h) != TYPE_DICTIONARY: continue
		if not (h.has("x") and h.has("z") and h.has("radius")): continue
		var radius := float(h.radius)
		if radius <= 0.0: continue
		var key := key_of(h)
		live[key] = true
		if not zones.has(key):
			zones[key] = _build(h, radius, terrain)
	for key in zones.keys():
		if not live.has(key):
			(zones[key].node as Node3D).queue_free()
			zones.erase(key)

func zone_keys() -> Array:
	return zones.keys()

func _build(h: Dictionary, radius: float, terrain) -> Dictionary:
	var phen := str(h.get("phenomenon", ""))
	var color := color_for(phen)
	var cx := float(h.x) + 0.5; var cz := float(h.z) + 0.5
	var verts := PackedVector3Array(); var colors := PackedColorArray(); var idx := PackedInt32Array()
	verts.append(Vector3(cx, terrain.height_at(cx, cz) + LIFT, cz)); colors.append(Color(color, 0.16))
	for ring in range(1, RINGS + 1):
		var f := float(ring) / RINGS
		var alpha := 0.16 + 0.22 * f * f + (0.3 if ring == RINGS else 0.0)      # a stronger rim marks exactly where the zone ends
		for s in SEGMENTS:
			var a := TAU * float(s) / SEGMENTS
			var x := cx + cos(a) * radius * f; var z := cz + sin(a) * radius * f
			verts.append(Vector3(x, terrain.height_at(x, z) + LIFT, z)); colors.append(Color(color, alpha))
	for s in SEGMENTS:
		idx.append_array([0, 1 + s, 1 + (s + 1) % SEGMENTS])
	for ring in range(1, RINGS):
		var a0 := 1 + (ring - 1) * SEGMENTS; var b0 := 1 + ring * SEGMENTS
		for s in SEGMENTS:
			var n := (s + 1) % SEGMENTS
			idx.append_array([a0 + s, b0 + s, b0 + n, a0 + s, b0 + n, a0 + n])
	var arrays := []
	arrays.resize(Mesh.ARRAY_MAX)
	arrays[Mesh.ARRAY_VERTEX] = verts; arrays[Mesh.ARRAY_COLOR] = colors; arrays[Mesh.ARRAY_INDEX] = idx
	var mesh := ArrayMesh.new()
	mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arrays)
	var mat := StandardMaterial3D.new()
	mat.vertex_color_use_as_albedo = true; mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED; mat.cull_mode = BaseMaterial3D.CULL_DISABLED
	mat.no_depth_test = false; mat.render_priority = 2
	var holder := Node3D.new()
	var mi := MeshInstance3D.new()
	mi.mesh = mesh; mi.material_override = mat; mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	holder.add_child(mi)
	var label := Label3D.new()
	label.text = word_for(phen); label.billboard = BaseMaterial3D.BILLBOARD_ENABLED; label.font_size = 56; label.pixel_size = 0.03
	label.modulate = Color(color.lerp(Color.WHITE, 0.45), 0.95); label.outline_size = 10; label.no_depth_test = true
	label.position = Vector3(cx, terrain.height_at(cx, cz) + 7.0, cz)
	holder.add_child(label)
	add_child(holder)
	return {"node": holder, "mat": mat, "phase": fposmod(cx * 0.37 + cz * 0.61, TAU)}

func _process(delta: float) -> void:
	_time += delta
	for z in zones.values():
		(z.mat as StandardMaterial3D).albedo_color.a = 0.8 + 0.2 * sin(_time * 3.0 + float(z.phase))
