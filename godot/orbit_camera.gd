extends Node3D
## Orbit / pan / zoom camera. Mouse: right-drag orbit, middle-drag or shift+left-drag pan, wheel zoom. Keys: WASD pan.

var yaw := -0.6
var pitch := -0.7
var distance := 60.0
var target := Vector3.ZERO
var camera := Camera3D.new()
var dragging_orbit := false
var dragging_pan := false
var touches := {}            # screen-touch index -> position, for phones: one finger orbits, two fingers pinch-zoom and pan
var pinch_distance := 0.0
var pinch_center := Vector2.ZERO

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

## Touch screens. One finger drags to orbit; two fingers pinch to zoom and drag to pan. (A tap still selects: Godot also sends it as a
## left click, which main.gd handles.) Pure arithmetic so it can be tested without a device.
static func pinch_zoom(distance: float, old_span: float, new_span: float) -> float:
	if old_span <= 1.0 or new_span <= 1.0:
		return distance
	return clampf(distance * old_span / new_span, 4.0, 900.0)

func _touch_event(event: InputEvent) -> bool:
	if event is InputEventScreenTouch:
		var t := event as InputEventScreenTouch
		if t.pressed:
			touches[t.index] = t.position
		else:
			touches.erase(t.index)
		if touches.size() == 2:
			var pts := touches.values()
			pinch_distance = (pts[0] as Vector2).distance_to(pts[1]); pinch_center = ((pts[0] as Vector2) + (pts[1] as Vector2)) * 0.5
		return true
	if event is InputEventScreenDrag:
		var d := event as InputEventScreenDrag
		touches[d.index] = d.position
		if touches.size() == 1:
			yaw -= d.relative.x * 0.006; pitch -= d.relative.y * 0.006; _apply()
		elif touches.size() == 2:
			var pts := touches.values()
			var span := (pts[0] as Vector2).distance_to(pts[1]); var center := ((pts[0] as Vector2) + (pts[1] as Vector2)) * 0.5
			distance = pinch_zoom(distance, pinch_distance, span)
			var right := global_transform.basis.x; var fwd := Vector3(-sin(yaw), 0, -cos(yaw)); var move := center - pinch_center
			target += (-right * move.x + fwd * move.y) * distance * 0.0016
			pinch_distance = span; pinch_center = center; _apply()
		return true
	return false

func _unhandled_input(event: InputEvent) -> void:
	if _touch_event(event):
		return
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
