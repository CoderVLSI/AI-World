extends Node3D
## Builds the land from /api/v1/terrain (the simulation's own heightmap and biomes).

const HEIGHT_SCALE := 1.6   # vertical exaggeration so relief is readable at world scale
const BIOME_COLORS := [Color("#4e8d99"), Color("#597665"), Color("#7f8b50"), Color("#526e46"), Color("#b3a277"), Color("#858778"), Color("#6f9440")]

var cols := 0
var rows := 0
var step := 2
var elev := PackedFloat32Array()
var world_w := 0
var world_d := 0

func build(t: Dictionary) -> void:
	for c in get_children():
		c.queue_free()
	cols = int(t.columns); rows = int(t.rows); step = int(t.step)
	world_w = int(t.width); world_d = int(t.depth)
	elev = PackedFloat32Array(t.elevation)
	var biome: Array = t.biome
	var verts := PackedVector3Array(); var colors := PackedColorArray(); var normals := PackedVector3Array()
	var idx := PackedInt32Array()
	for r in rows:
		for c in cols:
			var i := r * cols + c
			verts.append(Vector3(c * step, elev[i] * HEIGHT_SCALE, r * step))
			var shade := 0.92 + 0.16 * fposmod(sin(float(c) * 12.9898 + float(r) * 78.233) * 43758.5453, 1.0)  # gentle texture
			colors.append(BIOME_COLORS[int(biome[i])] * shade)
			var hl := elev[r * cols + maxi(c - 1, 0)]; var hr := elev[r * cols + mini(c + 1, cols - 1)]
			var hd := elev[maxi(r - 1, 0) * cols + c]; var hu := elev[mini(r + 1, rows - 1) * cols + c]
			normals.append(Vector3((hl - hr) * HEIGHT_SCALE, 2.0 * step, (hd - hu) * HEIGHT_SCALE).normalized())
	for r in rows - 1:
		for c in cols - 1:
			var a := r * cols + c; var b := a + 1; var d := a + cols; var e := d + 1
			idx.append_array([a, b, d, b, e, d])
	var arrays := []
	arrays.resize(Mesh.ARRAY_MAX)
	arrays[Mesh.ARRAY_VERTEX] = verts; arrays[Mesh.ARRAY_NORMAL] = normals
	arrays[Mesh.ARRAY_COLOR] = colors; arrays[Mesh.ARRAY_INDEX] = idx
	var mesh := ArrayMesh.new()
	mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arrays)
	var mat := StandardMaterial3D.new()
	mat.vertex_color_use_as_albedo = true; mat.roughness = 1.0; mat.cull_mode = BaseMaterial3D.CULL_DISABLED
	var mi := MeshInstance3D.new()
	mi.mesh = mesh; mi.material_override = mat
	add_child(mi)

func height_at(wx: float, wz: float) -> float:
	if cols < 2:
		return 0.0
	var gx := clampf(wx / step, 0.0, cols - 1.001); var gz := clampf(wz / step, 0.0, rows - 1.001)
	var x0 := int(gx); var z0 := int(gz); var fx := gx - x0; var fz := gz - z0
	var h00 := elev[z0 * cols + x0]; var h10 := elev[z0 * cols + x0 + 1]
	var h01 := elev[(z0 + 1) * cols + x0]; var h11 := elev[(z0 + 1) * cols + x0 + 1]
	return lerpf(lerpf(h00, h10, fx), lerpf(h01, h11, fx), fz) * HEIGHT_SCALE
