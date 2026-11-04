extends SceneTree
## Run: godot --headless --path godot --script res://tests/hazard_test.gd
## Hazard zones appear for what the API lists, follow the ground, are coloured and named by phenomenon, and disappear when the list drops them.
const HazardView := preload("res://hazard_view.gd")
var failures := 0

class StubTerrain extends RefCounted:
	func height_at(x: float, _z: float) -> float:
		return x * 0.1            # a slope, so a flat disc would be wrong

func check(cond: bool, what: String) -> void:
	if not cond:
		failures += 1; print("FAIL: ", what)

func _initialize() -> void:
	var root := Node3D.new(); get_root().add_child(root)
	var view := HazardView.new(); root.add_child(view)
	await process_frame
	var fire := {"phenomenon": "wildfire", "x": 40, "z": 50, "radius": 12.0, "strength": 1.0, "start_tick": 7}
	var flood := {"phenomenon": "floodwater", "x": 100, "z": 20, "radius": 20.0, "strength": 0.5, "start_tick": 7}
	view.update_hazards([], StubTerrain.new())
	check(view.zone_keys().is_empty(), "nothing listed, nothing drawn")
	view.update_hazards([fire, flood], StubTerrain.new())
	check(view.zone_keys().size() == 2, "two zones drawn (got %d)" % view.zone_keys().size())
	# the same list again does not duplicate or rebuild
	var first = view.zones[HazardView.key_of(fire)].node
	view.update_hazards([fire, flood], StubTerrain.new())
	check(view.zone_keys().size() == 2 and view.zones[HazardView.key_of(fire)].node == first, "a repeated poll changes nothing")
	# the disc reaches the radius, sits above and follows the sloping ground
	var mesh: ArrayMesh = (first.get_child(0) as MeshInstance3D).mesh
	var verts: PackedVector3Array = mesh.surface_get_arrays(0)[Mesh.ARRAY_VERTEX]
	var maxd := 0.0; var follows := true
	for v in verts:
		maxd = maxf(maxd, Vector2(v.x - 40.5, v.z - 50.5).length())
		if absf(v.y - (v.x * 0.1 + HazardView.LIFT)) > 0.001: follows = false
	check(absf(maxd - 12.0) < 0.01, "the disc's edge is at the stated radius (got %f)" % maxd)
	check(follows, "every vertex follows the ground height")
	# colour and word by phenomenon
	check(HazardView.word_for("mystery") == "mystery", "an unknown phenomenon keeps its own name")
	var seen := {}
	for ph in ["wildfire", "floodwater", "heatwave", "severe storm"]:
		check(HazardView.color_for(ph) != HazardView.FALLBACK, ph + " has its own colour")
		seen[HazardView.color_for(ph)] = true
	check(seen.size() == 4, "four hazard kinds, four colours")
	var label := first.get_child(1) as Label3D
	check(label.text == "wildfire", "the label names the zone")
	# a zone the API stops listing goes away; bad entries are ignored
	view.update_hazards([flood, {"phenomenon": "wildfire"}, {"phenomenon": "x", "x": 1, "z": 1, "radius": 0}, "junk"], StubTerrain.new())
	check(view.zone_keys() == [HazardView.key_of(flood)], "only the listed zone remains (got %s)" % str(view.zone_keys()))
	view.update_hazards([], StubTerrain.new())
	check(view.zone_keys().is_empty(), "an empty list clears the zones")
	print("hazard tests: ", "ok" if failures == 0 else "FAILED")
	quit(1 if failures > 0 else 0)
