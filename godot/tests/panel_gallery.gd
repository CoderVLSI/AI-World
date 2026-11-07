extends SceneTree
## Renders the server-address panel to a PNG:  OUT=/abs/path.png xvfb-run -a godot --path godot --rendering-driver opengl3 --resolution 1600x720 --script res://tests/panel_gallery.gd
const ConnectPanel := preload("res://connect_panel.gd")

func _initialize() -> void:
	var bg := ColorRect.new(); bg.color = Color("#17241d"); bg.set_anchors_preset(Control.PRESET_FULL_RECT)
	get_root().add_child(bg)
	var panel := ConnectPanel.new(); get_root().add_child(panel)
	await process_frame
	panel.open("100.64.0.5:8000")
	await process_frame; await process_frame
	var out := OS.get_environment("OUT")
	get_root().get_texture().get_image().save_png(out if out != "" else "panel.png")
	print("saved ", out)
	quit()
