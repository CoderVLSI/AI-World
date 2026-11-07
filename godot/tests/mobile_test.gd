extends SceneTree
## Run: godot --headless --path godot --script res://tests/mobile_test.gd
## Phone support: the server-address panel, and one-finger orbit / two-finger pinch-zoom and pan on the camera.
const ConnectPanel := preload("res://connect_panel.gd")
const OrbitCamera := preload("res://orbit_camera.gd")
var failures := 0
var got: Array = []

func check(cond: bool, what: String) -> void:
	if not cond:
		failures += 1; print("FAIL: ", what)

func _initialize() -> void:
	# address handling
	check(ConnectPanel.normalize("100.64.0.5") == "http://100.64.0.5:8000", "a bare address gets the scheme and the usual port")
	check(ConnectPanel.normalize("  100.64.0.5:9000 ") == "http://100.64.0.5:9000", "spaces are trimmed and an explicit port is kept")
	check(ConnectPanel.normalize("http://my-laptop.tailnet.ts.net:8000/") == "http://my-laptop.tailnet.ts.net:8000", "scheme kept, trailing slash dropped")
	check(ConnectPanel.normalize("https://example.org") == "https://example.org", "https is left alone")
	for bad in ["", "   ", ":8000", "host name", "http://"]:
		check(ConnectPanel.normalize(bad) == "", "not an address: '%s'" % bad)
	# remembered address
	var before := ConnectPanel.load_saved()
	ConnectPanel.save("http://10.1.2.3:8000")
	check(ConnectPanel.load_saved() == "http://10.1.2.3:8000", "the address is remembered")
	ConnectPanel.save(before)
	# the panel
	var root := Node3D.new(); get_root().add_child(root)
	var panel := ConnectPanel.new(); root.add_child(panel)
	panel.submitted.connect(func(u): got.append(u))
	await process_frame
	panel.open("")
	check(panel.panel.visible and not panel.change_button.visible, "open shows the panel")
	panel.edit.text = "nonsense with spaces"; panel._submit()
	check(got.is_empty() and panel.status.text != "" and panel.panel.visible, "a bad address is refused with a message and nothing is sent")
	panel.edit.text = "100.64.0.5"; panel._submit()
	check(got == ["http://100.64.0.5:8000"] and not panel.panel.visible and panel.change_button.visible, "a good address connects and leaves a button to change it")
	ConnectPanel.save(before)
	# camera arithmetic
	check(OrbitCamera.pinch_zoom(100.0, 100.0, 200.0) == 50.0, "fingers apart: zoom in")
	check(OrbitCamera.pinch_zoom(100.0, 200.0, 100.0) == 200.0, "fingers together: zoom out")
	check(OrbitCamera.pinch_zoom(100.0, 0.5, 200.0) == 100.0 and OrbitCamera.pinch_zoom(100.0, 100.0, 0.0) == 100.0, "degenerate spans change nothing")
	check(OrbitCamera.pinch_zoom(5.0, 100.0, 1000.0) == 4.0 and OrbitCamera.pinch_zoom(800.0, 100.0, 10.0) == 900.0, "zoom stays within limits")
	# camera gestures
	var cam := OrbitCamera.new(); root.add_child(cam)
	await process_frame
	var yaw0 := cam.yaw; var pitch0 := cam.pitch
	var t0 := InputEventScreenTouch.new(); t0.index = 0; t0.pressed = true; t0.position = Vector2(300, 300); cam._unhandled_input(t0)
	var d0 := InputEventScreenDrag.new(); d0.index = 0; d0.position = Vector2(340, 330); d0.relative = Vector2(40, 30); cam._unhandled_input(d0)
	check(not is_equal_approx(cam.yaw, yaw0) and not is_equal_approx(cam.pitch, pitch0), "one finger drag orbits")
	var dist0 := cam.distance; var target0 := cam.target
	var t1 := InputEventScreenTouch.new(); t1.index = 1; t1.pressed = true; t1.position = Vector2(400, 300); cam._unhandled_input(t1)
	var d1 := InputEventScreenDrag.new(); d1.index = 1; d1.position = Vector2(600, 300); d1.relative = Vector2(200, 0); cam._unhandled_input(d1)
	check(cam.distance < dist0, "two fingers moving apart zoom in (%f -> %f)" % [dist0, cam.distance])
	var yaw1 := cam.yaw
	var d2 := InputEventScreenDrag.new(); d2.index = 0; d2.position = Vector2(340, 400); d2.relative = Vector2(0, 70); cam._unhandled_input(d2)
	check(is_equal_approx(cam.yaw, yaw1), "with two fingers down a drag does not orbit")
	var up := InputEventScreenTouch.new(); up.index = 1; up.pressed = false; cam._unhandled_input(up)
	up = InputEventScreenTouch.new(); up.index = 0; up.pressed = false; cam._unhandled_input(up)
	check(cam.touches.is_empty(), "lifting both fingers clears the touches")
	print("mobile tests: ", "ok" if failures == 0 else "FAILED")
	quit(1 if failures > 0 else 0)
