extends SceneTree
## Renders every species side by side for a visual check (display only; not part of the viewer).
## Run: OUT=docs/images/animals_gallery.png xvfb-run -a godot --path godot --rendering-driver opengl3 --script res://tests/animal_gallery.gd
const Builder := preload("res://animal_builder.gd")
const Motion := preload("res://animal_motion.gd")
func _initialize() -> void:
	var b := Builder.new()
	var species := [["deer","mammal","#d6b78a"],["rabbit","mammal","#ddd3bb"],["boar","mammal","#9e8273"],["wolf","mammal","#a7b8bd"],["fox","mammal","#e5a16b"],["sparrow","bird","#d0bb8c"],["crow","bird","#7a8790"],["duck","bird","#9cccab"],["owl","bird","#c9b7a6"],["carp","fish","#94c9d6"],["butterfly","insect","#d2afe1"],["bee","insect","#e0cc78"]]
	var root := Node3D.new(); get_root().add_child(root)
	var env := Environment.new(); env.background_mode = Environment.BG_COLOR; env.background_color = Color("#9fc6e0")
	env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR; env.ambient_light_color = Color(0.9,0.9,0.9)
	var we := WorldEnvironment.new(); we.environment = env; root.add_child(we)
	var sun := DirectionalLight3D.new(); sun.rotation_degrees = Vector3(-50, 30, 0); root.add_child(sun)
	var ground := MeshInstance3D.new(); var pm := PlaneMesh.new(); pm.size = Vector2(60, 16); ground.mesh = pm
	var gm := StandardMaterial3D.new(); gm.albedo_color = Color("#6b8f4e"); ground.material_override = gm; root.add_child(ground)
	var i := 0
	for s in species:
		var n: Node3D = b.build(s[0], s[1], s[2], "male")
		var col := i % 6; var row := i / 6
		n.position = Vector3(-8.0 + col * 3.2, 0, -2.5 + row * 4.2)
		n.rotation.y = deg_to_rad(-60)
		var action := "roaming"
		b.apply_pose(n, Motion.pose(s[1], action, false, 0.3)); if s[1] == "fish" or s[1] == "insect": n.get_meta("parts").rig.position.y = 0.4
		root.add_child(n); i += 1
	var cam := Camera3D.new(); root.add_child(cam); var cp := Vector3(0, 8.0, 8.5); var tgt := Vector3(0, 0.2, 1.2); cam.transform = Transform3D(Basis.looking_at(tgt - cp, Vector3.UP), cp); cam.fov = 62; cam.current = true
	await process_frame; await process_frame; await process_frame
	get_root().get_texture().get_image().save_png(OS.get_environment("OUT"))
	quit()
