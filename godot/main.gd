extends Node3D
## CAITANYA witness client. Fetches the static terrain once, then polls /api/v1/live. GET requests only.

const TerrainView := preload("res://terrain_view.gd")
const Actors := preload("res://actors.gd")
const OrbitCamera := preload("res://orbit_camera.gd")
const Hud := preload("res://hud.gd")

var server := "http://127.0.0.1:8000"
var poll_seconds := 1.0
var screenshot_path := ""
var screenshot_wait := 6.0
var terrain := {}
var live := {}
var terrain_view := TerrainView.new()
var actors := Actors.new()
var cam := OrbitCamera.new()
var hud := Hud.new()
var sun := DirectionalLight3D.new()
var env := Environment.new()
var since_poll := 99.0
var busy := false
var connected := false
var framed := false
var shot_timer := -1.0
var selected := ""

func _ready() -> void:
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--server="): server = arg.substr(9).rstrip("/")
		elif arg.begins_with("--screenshot="): screenshot_path = arg.substr(13)
		elif arg.begins_with("--wait="): screenshot_wait = float(arg.substr(7))
		elif arg.begins_with("--poll="): poll_seconds = float(arg.substr(7))
		elif arg.begins_with("--select="): selected = arg.substr(9)
	var we := WorldEnvironment.new()
	env.background_mode = Environment.BG_COLOR; env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.fog_enabled = true; env.fog_density = 0.0016
	we.environment = env; add_child(we)
	sun.shadow_enabled = false; add_child(sun)
	add_child(terrain_view); add_child(actors); add_child(cam); add_child(hud)
	actors.terrain = terrain_view
	_apply_sky(12.0)

func _get_json(path: String):
	var http := HTTPRequest.new()
	http.timeout = 20.0
	add_child(http)
	if http.request(server + path) != OK:      # default method is GET; this client never sends anything else
		http.queue_free(); return null
	var res: Array = await http.request_completed
	http.queue_free()
	if res[0] != HTTPRequest.RESULT_SUCCESS or res[1] != 200: return null
	return JSON.parse_string((res[3] as PackedByteArray).get_string_from_utf8())

func _poll() -> void:
	busy = true
	if terrain.is_empty():
		var t = await _get_json("/api/v1/terrain?step=2")
		if t != null:
			terrain = t; terrain_view.build(t)
	var data = await _get_json("/api/v1/live")
	connected = data != null and not terrain.is_empty()
	if connected:
		live = data
		actors.update_live(live, terrain_view)
		var c = live.get("climate")
		if c != null: _apply_sky(float(c.get("hour", 12.0)))
		if not framed and not actors.people.is_empty():
			cam.focus(actors.centroid(), 55.0); framed = true; shot_timer = 0.0
		actors.selected = selected
		hud.show_selected(actors.latest_people.get(selected))
	hud.show_live(live, connected)
	busy = false; since_poll = 0.0

func _apply_sky(hour: float) -> void:
	var t := (hour - 6.0) / 12.0
	var elev := sin(clampf(t, 0.0, 1.0) * PI) if t >= 0.0 and t <= 1.0 else 0.0
	sun.rotation_degrees = Vector3(-(12.0 + 68.0 * elev), clampf(t, 0.0, 1.0) * 180.0 - 90.0, 0.0)
	sun.light_energy = lerpf(0.2, 1.3, elev)
	var sky := Color(0.02, 0.04, 0.09).lerp(Color(0.52, 0.72, 0.9), elev)
	env.background_color = sky; env.fog_light_color = sky
	env.ambient_light_color = Color(0.45, 0.5, 0.6).lerp(Color(0.85, 0.85, 0.8), elev)
	env.ambient_light_energy = lerpf(0.6, 1.0, elev)

func _process(delta: float) -> void:
	since_poll += delta
	if not busy and since_poll >= poll_seconds:
		_poll()
	if shot_timer >= 0.0 and screenshot_path != "":
		shot_timer += delta
		if shot_timer >= screenshot_wait:
			shot_timer = -1.0; _save_and_quit()

func _save_and_quit() -> void:
	await RenderingServer.frame_post_draw
	get_viewport().get_texture().get_image().save_png(screenshot_path)
	print("SCREENSHOT ", screenshot_path)
	get_tree().quit()

func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventMouseButton and event.pressed and event.button_index == MOUSE_BUTTON_LEFT and not event.shift_pressed:
		selected = actors.pick(cam.camera, event.position); actors.selected = selected
		hud.show_selected(actors.latest_people.get(selected))
	elif event is InputEventKey and event.pressed and event.keycode == KEY_F:
		cam.focus(actors.centroid(), 45.0)
