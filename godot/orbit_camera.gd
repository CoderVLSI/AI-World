extends Node3D
## Orbit / pan / zoom camera. Mouse: right-drag orbit, middle-drag or shift+left-drag pan, wheel zoom. Keys: WASD pan.

var yaw := -0.6
var pitch := -0.7
var distance := 60.0
var target := Vector3.ZERO
var camera := Camera3D.new()
var dragging_orbit := false
var dragging_pan := false

func _ready() -> void:
	camera.far = 2500.0; camera.near = 0.1; camera.fov = 55.0
	add_child(camera)
	_apply()

func focus(pos: Vector3, dist: float) -> void:
	target = pos; distance = dist; _apply()

func _apply() -> void:
	pitch = clampf(pitch, -1.5, -0.08)
	distance = clampf(distance, 4.0, 900.0)
	global_position = target
	rotation = Vector3(pitch, yaw, 0.0)
	camera.position = Vector3(0, 0, distance)

func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventMouseButton:
		var e := event as InputEventMouseButton
		if e.button_index == MOUSE_BUTTON_RIGHT: dragging_orbit = e.pressed
		elif e.button_index == MOUSE_BUTTON_MIDDLE: dragging_pan = e.pressed
		elif e.button_index == MOUSE_BUTTON_LEFT: dragging_pan = e.pressed and e.shift_pressed
		elif e.button_index == MOUSE_BUTTON_WHEEL_UP and e.pressed: distance *= 0.9; _apply()
		elif e.button_index == MOUSE_BUTTON_WHEEL_DOWN and e.pressed: distance *= 1.1; _apply()
	elif event is InputEventMouseMotion:
		var m := event as InputEventMouseMotion
		if dragging_orbit:
			yaw -= m.relative.x * 0.005; pitch -= m.relative.y * 0.005; _apply()
		elif dragging_pan:
			var right := global_transform.basis.x; var fwd := Vector3(-sin(yaw), 0, -cos(yaw))
			target += (-right * m.relative.x + fwd * m.relative.y) * distance * 0.0016; _apply()

func _process(delta: float) -> void:
	var move := Vector3.ZERO
	var fwd := Vector3(-sin(yaw), 0, -cos(yaw)); var right := Vector3(cos(yaw), 0, -sin(yaw))
	if Input.is_key_pressed(KEY_W): move += fwd
	if Input.is_key_pressed(KEY_S): move -= fwd
	if Input.is_key_pressed(KEY_D): move += right
	if Input.is_key_pressed(KEY_A): move -= right
	if move != Vector3.ZERO:
		target += move.normalized() * distance * 0.8 * delta; _apply()
