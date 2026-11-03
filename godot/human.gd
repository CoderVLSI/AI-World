extends Node3D
## A person built from primitives, drawn from the simulation's recorded age, height, gender, skin and clothing.
## Proportions follow age (human_proportions.gd) and update in place, so one person visibly grows. Poses come
## from the same recorded-state rule as everyone else (animation_map.gd): nothing is invented.

const Props := preload("res://human_proportions.gd")
const METRE := 1.6          # display units per metre, same as the animals and animated models

var parts := {}
var skin := Color("#bd8c68")
var cloth := Color("#678b91")
var hair := Color("#2b2118")
var gender := ""
var age := -1.0
var height_cm := -1.0
var props := {}
var lens := {}              # current segment lengths (display units)
var state := "idle"
var phase := 0.0
var clock := 0.0
var cur := {}               # smoothed joint angles
var _mats := {}

func _mat(c: Color) -> StandardMaterial3D:
	var key := c.to_html()
	if not _mats.has(key):
		var m := StandardMaterial3D.new(); m.albedo_color = c; m.roughness = 0.9
		_mats[key] = m
	return _mats[key]

func _pivot(parent: Node3D) -> Node3D:
	var n := Node3D.new(); parent.add_child(n)
	return n

func _ball(parent: Node3D, c: Color) -> MeshInstance3D:
	var mi := MeshInstance3D.new(); var sm := SphereMesh.new()
	sm.radius = 0.5; sm.height = 1.0; sm.radial_segments = 10; sm.rings = 5
	mi.mesh = sm; mi.material_override = _mat(c); parent.add_child(mi)
	return mi

func _tube(parent: Node3D, c: Color) -> MeshInstance3D:
	var mi := MeshInstance3D.new(); var cm := CylinderMesh.new()
	cm.top_radius = 0.5; cm.bottom_radius = 0.42; cm.height = 1.0; cm.radial_segments = 8
	mi.mesh = cm; mi.material_override = _mat(c); parent.add_child(mi)
	return mi

## `agent` is one entry of /api/v1/live agents.
func setup(agent: Dictionary) -> void:
	skin = Color(str(agent.get("skin_tone", "#bd8c68")))
	cloth = Color(str(agent.get("clothing_color", "#678b91")))
	gender = str(agent.get("gender", ""))
	var digits := str(agent.get("id", "0")).get_slice("-", 1)
	var tone := int(digits) % 3                      # hair colour is a display choice, varied by id
	hair = [Color("#2b2118"), Color("#4a3322"), Color("#16120f")][tone]
	phase = float(hash(str(agent.get("id"))) % 628) / 100.0
	var rig := _pivot(self); parts["rig"] = rig
	var hips := _pivot(rig); parts["hips"] = hips
	parts["pelvis"] = _ball(hips, cloth.darkened(0.25))
	var torso_pivot := _pivot(hips); parts["torso_pivot"] = torso_pivot
	parts["torso"] = _ball(torso_pivot, cloth)
	parts["neck"] = _tube(torso_pivot, skin)
	var head_pivot := _pivot(torso_pivot); parts["head_pivot"] = head_pivot
	parts["head"] = _ball(head_pivot, skin)
	parts["hair"] = _ball(head_pivot, hair)
	parts["eye_l"] = _ball(head_pivot, Color("#1d1b1a")); parts["eye_r"] = _ball(head_pivot, Color("#1d1b1a"))
	for side in ["l", "r"]:
		var shoulder := _pivot(torso_pivot); parts["arm_" + side] = shoulder
		parts["upper_arm_" + side] = _tube(shoulder, cloth)
		var elbow := _pivot(shoulder); parts["elbow_" + side] = elbow
		parts["forearm_" + side] = _tube(elbow, skin)
		parts["hand_" + side] = _ball(elbow, skin)
		var hip := _pivot(hips); parts["hip_" + side] = hip
		parts["thigh_" + side] = _tube(hip, cloth.darkened(0.25))
		var knee := _pivot(hip); parts["knee_" + side] = knee
		parts["shin_" + side] = _tube(knee, cloth.darkened(0.25))
		parts["foot_" + side] = _ball(knee, Color("#2a2522"))
	for j in ["hip_l", "hip_r", "knee_l", "knee_r", "arm_l", "arm_r", "elbow_l", "elbow_r", "torso", "pitch", "yaw", "sit"]:
		cur[j] = 0.0
	set_growth(float(agent.get("age_years", 25.0)), float(agent.get("height_cm", 170.0)))

func top_y() -> float:
	return float(lens.get("height", 2.7))

## Re-shape the body for a new age/height. Cheap, and a no-op when nothing meaningful changed.
func set_growth(age_years: float, height_in_cm: float) -> void:
	if absf(age_years - age) < 0.01 and absf(height_in_cm - height_cm) < 0.5:
		return
	age = age_years; height_cm = height_in_cm
	props = Props.proportions(age, gender)
	var h := maxf(height_cm, 30.0) / 100.0 * METRE
	var head_h: float = props.head * h
	var leg_len: float = props.leg * h
	var torso_len: float = props.torso * h
	var neck_len: float = props.neck * h
	var arm_len: float = props.arm * h
	var girth: float = props.girth
	var depth := 0.105 * h * girth
	var sh_w: float = props.shoulder * h
	var hip_w: float = props.hip * h
	lens = {"height": h, "head": head_h, "leg": leg_len, "torso": torso_len, "neck": neck_len, "arm": arm_len, "thigh": leg_len * 0.5,
		"shin": leg_len * 0.5 - 0.035 * h, "upper": arm_len * 0.46, "fore": arm_len * 0.54 - 0.02 * h}
	parts.hips.position = Vector3(0, leg_len, 0)
	parts.pelvis.scale = Vector3(hip_w * 1.05, 0.09 * h, depth * 0.95); parts.pelvis.position = Vector3(0, 0.0, 0)
	parts.torso.scale = Vector3(sh_w * 1.05, torso_len * 1.04, depth); parts.torso.position = Vector3(0, torso_len * 0.5, 0)
	parts.neck.scale = Vector3(0.05 * h * girth, neck_len * 1.6, 0.05 * h * girth); parts.neck.position = Vector3(0, torso_len + neck_len * 0.4, 0)
	parts.head_pivot.position = Vector3(0, torso_len + neck_len, 0)
	parts.head.scale = Vector3(head_h * 0.82, head_h, head_h * 0.9); parts.head.position = Vector3(0, head_h * 0.5, 0)
	var grey: float = props.grey
	parts.hair.material_override = _mat(hair.lerp(Color("#cfcfcf"), grey))
	parts.hair.scale = Vector3(head_h * 0.86, head_h * 0.64, head_h * 0.94); parts.hair.position = Vector3(0, head_h * 0.7, -head_h * 0.05)
	for side in ["l", "r"]:
		var sgn := -1.0 if side == "l" else 1.0
		parts["arm_" + side].position = Vector3(sgn * sh_w * 0.52, torso_len - 0.03 * h, 0)
		parts["upper_arm_" + side].scale = Vector3(0.05 * h, lens.upper, 0.05 * h)
		parts["upper_arm_" + side].position = Vector3(0, -lens.upper * 0.5, 0)
		parts["elbow_" + side].position = Vector3(0, -lens.upper, 0)
		parts["forearm_" + side].scale = Vector3(0.042 * h, lens.fore, 0.042 * h)
		parts["forearm_" + side].position = Vector3(0, -lens.fore * 0.5, 0)
		parts["hand_" + side].scale = Vector3(0.05 * h, 0.05 * h, 0.05 * h)
		parts["hand_" + side].position = Vector3(0, -lens.fore - 0.01 * h, 0)
		parts["hip_" + side].position = Vector3(sgn * hip_w * 0.3, 0, 0)
		parts["thigh_" + side].scale = Vector3(0.075 * h, lens.thigh, 0.075 * h * girth)
		parts["thigh_" + side].position = Vector3(0, -lens.thigh * 0.5, 0)
		parts["knee_" + side].position = Vector3(0, -lens.thigh, 0)
		parts["shin_" + side].scale = Vector3(0.06 * h, lens.shin, 0.06 * h * girth)
		parts["shin_" + side].position = Vector3(0, -lens.shin * 0.5, 0)
		parts["foot_" + side].scale = Vector3(0.07 * h, 0.045 * h, 0.13 * h)
		parts["foot_" + side].position = Vector3(0, -lens.shin - 0.01 * h, 0.03 * h)
		parts["eye_" + side].scale = Vector3(1, 1, 1) * head_h * 0.1
		parts["eye_" + side].position = Vector3(sgn * head_h * 0.2, head_h * 0.55, head_h * 0.4)

func play_state(s: String) -> void:
	state = s

## Target joint angles (radians) for a state at time t. Pure: only the recorded state and the clock matter.
static func targets(s: String, t: float, stoop: float, infant: bool) -> Dictionary:
	var d := {"hip_l": 0.0, "hip_r": 0.0, "knee_l": 0.0, "knee_r": 0.0, "arm_l": 0.0, "arm_r": 0.0, "elbow_l": -0.1, "elbow_r": -0.1,
		"torso": stoop, "pitch": 0.0, "yaw": 0.0, "sit": 0.0, "bob": 0.0}
	match s:
		"walk":
			var w := t * (9.0 if infant else 7.0)
			d.hip_l = sin(w) * 0.6; d.hip_r = -sin(w) * 0.6
			d.knee_l = maxf(0.0, sin(w - 0.9)) * 0.9; d.knee_r = maxf(0.0, -sin(w - 0.9)) * 0.9
			d.arm_l = -sin(w) * 0.5; d.arm_r = sin(w) * 0.5; d.elbow_l = -0.3; d.elbow_r = -0.3
			d.bob = absf(sin(w)) * 0.02
		"rest":                                       # sitting on the ground, legs forward
			d.hip_l = -1.45; d.hip_r = -1.45; d.knee_l = 0.15; d.knee_r = 0.15; d.sit = 1.0
			d.arm_l = -0.35; d.arm_r = -0.35; d.elbow_l = -0.9; d.elbow_r = -0.9; d.pitch = 0.2
		"talk":
			d.arm_r = -1.0 + sin(t * 3.0) * 0.3; d.elbow_r = -0.9; d.arm_l = -0.2
			d.pitch = sin(t * 3.0) * 0.08; d.yaw = sin(t * 0.8) * 0.3
		"work":                                       # bent over, hands working low
			d.torso = stoop + 0.7; d.hip_l = -0.35; d.hip_r = -0.35; d.knee_l = 0.7; d.knee_r = 0.7
			d.arm_l = -0.9 + sin(t * 4.0) * 0.2; d.arm_r = -0.9 - sin(t * 4.0) * 0.2; d.elbow_l = -0.4; d.elbow_r = -0.4; d.pitch = 0.2
		"eat":
			d.arm_r = -0.5; d.elbow_r = -2.0 + sin(t * 3.0) * 0.15; d.pitch = -0.1
		_:                                            # idle: breathing and a slow look around
			d.torso = stoop + sin(t * 1.4) * 0.012; d.pitch = sin(t * 0.7) * 0.06; d.yaw = sin(t * 0.4) * 0.25
			d.arm_l = sin(t * 1.1) * 0.05; d.arm_r = -sin(t * 1.1) * 0.05
	return d

func _process(delta: float) -> void:
	if parts.is_empty() or lens.is_empty():
		return
	clock += delta
	var goal := targets(state, clock + phase, float(props.get("stoop", 0.0)), age < 1.5)
	var k := 1.0 - exp(-12.0 * delta)
	for j in ["hip_l", "hip_r", "knee_l", "knee_r", "arm_l", "arm_r", "elbow_l", "elbow_r", "torso", "pitch", "yaw", "sit"]:
		cur[j] = lerpf(float(cur[j]), float(goal[j]), k)
	parts.hip_l.rotation.x = cur.hip_l; parts.hip_r.rotation.x = cur.hip_r
	parts.knee_l.rotation.x = cur.knee_l; parts.knee_r.rotation.x = cur.knee_r
	parts.arm_l.rotation.x = cur.arm_l; parts.arm_r.rotation.x = cur.arm_r
	parts.elbow_l.rotation.x = cur.elbow_l; parts.elbow_r.rotation.x = cur.elbow_r
	parts.torso_pivot.rotation.x = cur.torso
	parts.head_pivot.rotation.x = cur.pitch; parts.head_pivot.rotation.y = cur.yaw
	# Keep the body on the ground: standing hips sit at leg length; sitting lowers them to the ground.
	var standing: float = float(lens.leg)
	var seated: float = 0.05 * float(lens.height)
	var y: float = lerpf(standing, seated, clampf(float(cur.sit), 0.0, 1.0))
	if float(cur.sit) < 0.5 and state == "work":
		y = float(lens.thigh) * cos(0.35) + float(lens.shin) * cos(0.35) + 0.035 * float(lens.height)
	parts.hips.position.y = y + float(goal.bob) * float(lens.height)
