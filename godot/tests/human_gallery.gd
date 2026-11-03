extends SceneTree
## Renders the same two people at growing ages for a visual check (display only; not part of the viewer).
## Run: OUT=docs/images/human_growth.png xvfb-run -a godot --path godot --rendering-driver opengl3 --script res://tests/human_gallery.gd
const Human := preload("res://human.gd")

# The simulation's own height rule for people born in the world: 50 + (adult - 50) * sqrt(years / 18).
func sim_height(age: float, adult: float) -> float:
	if age >= 18.0:
		return adult
	return 50.0 + (adult - 50.0) * sqrt(age / 18.0)

func _initialize() -> void:
	var ages := [0.5, 2.0, 6.0, 12.0, 18.0, 30.0, 55.0, 80.0]
	var root := Node3D.new(); get_root().add_child(root)
	var env := Environment.new(); env.background_mode = Environment.BG_COLOR; env.background_color = Color("#9fc6e0")
	env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR; env.ambient_light_color = Color(0.9, 0.9, 0.9)
	var we := WorldEnvironment.new(); we.environment = env; root.add_child(we)
	var sun := DirectionalLight3D.new(); sun.rotation_degrees = Vector3(-50, 25, 0); root.add_child(sun)
	var ground := MeshInstance3D.new(); var pm := PlaneMesh.new(); pm.size = Vector2(60, 20); ground.mesh = pm
	var gm := StandardMaterial3D.new(); gm.albedo_color = Color("#6b8f4e"); ground.material_override = gm; root.add_child(ground)
	var people := [
		{"id": "agent-0002", "gender": "woman", "skin_tone": "#8d5c40", "clothing_color": "#8e709d", "adult": 164.0, "z": 2.4},
		{"id": "agent-0003", "gender": "man", "skin_tone": "#e4bc98", "clothing_color": "#678b91", "adult": 181.0, "z": -2.4}]
	for p in people:
		for i in ages.size():
			var age: float = ages[i]
			var a: Dictionary = {"id": p.id, "gender": p.gender, "skin_tone": p.skin_tone, "clothing_color": p.clothing_color,
				"age_years": age, "height_cm": sim_height(age, float(p.adult))}
			var n: Node3D = Human.new(); n.setup(a); root.add_child(n)
			n.position = Vector3(-7.0 + i * 2.0, 0, float(p.z) * 1.3)
			n.rotation.y = deg_to_rad(15)
			n._process(0.5)
	var cam := Camera3D.new(); root.add_child(cam)
	var cp := Vector3(0, 7.2, 11.5); var tgt := Vector3(0, 0.9, 0)
	cam.transform = Transform3D(Basis.looking_at(tgt - cp, Vector3.UP), cp); cam.fov = 50; cam.current = true
	await process_frame; await process_frame; await process_frame
	get_root().get_texture().get_image().save_png(OS.get_environment("OUT"))
	quit()
