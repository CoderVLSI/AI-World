extends RefCounted
## Pose of an animal for one moment, as a pure function of what the simulation RECORDED (its `action`) and whether
## it is really moving. Nothing is invented: an unknown action is an idle animal, and an action the simulation
## never records for a species is never played for it.

# Every action string fauna/ecology.py can record. A test cross-checks this list against the engine source.
const ACTIONS := ["roaming", "foraging", "hunting", "resting", "swimming", "flying", "avoiding predator", "grazing aquatic food"]

static func pose(group: String, action: String, moving: bool, t: float) -> Dictionary:
	var p := {"leg": 0.0, "head_pitch": 0.0, "tail_yaw": 0.0, "wing": 0.0, "drop": 0.0, "bob": 0.0,
		"hover": 0.0, "body_pitch": 0.0, "sway": 0.0}
	match group:
		"fish":
			var rate := 7.0 if (moving or action == "avoiding predator") else 3.0
			p.tail_yaw = sin(t * rate) * 0.55
			p.sway = sin(t * rate) * 0.12
			p.hover = -0.25
		"insect":
			var butterfly_rate := 14.0
			if action == "resting":
				p.hover = 0.0
				p.wing = -1.1 + sin(t * 0.8) * 0.05                # wings held up together at rest
			else:
				p.wing = sin(t * butterfly_rate) * 0.85
				p.hover = 0.9 + sin(t * 2.1) * 0.12
		"bird":
			var airborne := action == "flying" or (action == "avoiding predator" and moving)
			p.wing = 1.3                                       # wings folded against the body unless beating
			if airborne:
				p.wing = sin(t * 20.0) * 0.9
				p.hover = 1.6
				p.body_pitch = -0.15
			elif action == "swimming":
				p.bob = sin(t * 2.0) * 0.02
			elif action == "resting":
				p.drop = 0.5
				p.head_pitch = 0.3
			elif moving:
				p.leg = sin(t * 10.0) * 0.5
				p.bob = absf(sin(t * 10.0)) * 0.03
			elif action == "foraging" or action == "grazing aquatic food":
				p.head_pitch = absf(sin(t * 4.0)) * 0.9      # pecking / dabbling
			else:
				p.head_pitch = sin(t * 1.3) * 0.12
			p.tail_yaw = sin(t * 2.0) * 0.1
		_:
			p.tail_yaw = sin(t * 3.0) * 0.25
			if action == "resting" and not moving:
				p.drop = 0.6
				p.head_pitch = 0.25
				p.tail_yaw = sin(t * 0.7) * 0.05
			elif moving:
				var stalking := action == "hunting"
				var fleeing := action == "avoiding predator"      # the engine's own record of moving away from a predator
				p.leg = sin(t * (14.0 if fleeing else 7.0 if stalking else 9.0)) * (0.9 if fleeing else 0.5 if stalking else 0.7)
				p.bob = absf(sin(t * 9.0)) * 0.04
				if stalking:
					p.head_pitch = 0.35
					p.drop = 0.25
			elif action == "foraging":
				p.head_pitch = 0.8 + sin(t * 2.0) * 0.08     # head to the ground
			elif action == "hunting":
				p.head_pitch = 0.3
				p.drop = 0.3
			else:
				p.bob = sin(t * 1.5) * 0.01
				p.head_pitch = sin(t * 0.7) * 0.1
	return p
