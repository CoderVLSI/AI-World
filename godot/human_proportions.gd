extends RefCounted
## Display proportions of a human body at a given age. These are approximate, stylised figures for drawing a
## recognisable infant, child, adolescent, adult or elder; they are not medical data and the simulation does not
## use them. Height itself always comes from the simulation (`height_cm`); only the SHAPE depends on age.
## Stage ages match caitanya/lifecycle.py stage() (a test cross-checks them).

const INFANT_MAX := 3.0
const CHILD_MAX := 13.0
const ADULT_FROM := 18.0
const ELDER_FROM := 65.0

# [age in years, value]. Head height, leg length and arm length are fractions of total standing height.
const HEAD := [[0.0, 0.25], [2.0, 0.20], [6.0, 0.17], [12.0, 0.15], [18.0, 0.135], [90.0, 0.14]]
const LEG := [[0.0, 0.30], [2.0, 0.34], [6.0, 0.40], [12.0, 0.45], [18.0, 0.48], [65.0, 0.48], [95.0, 0.45]]
const ARM := [[0.0, 0.34], [6.0, 0.38], [12.0, 0.41], [18.0, 0.44]]
const SHOULDER := [[0.0, 0.21], [6.0, 0.20], [12.0, 0.21], [18.0, 0.24]]
const GIRTH := [[0.0, 1.30], [3.0, 1.12], [8.0, 0.95], [18.0, 1.0]]
const NECK := 0.03

static func table(t: Array, x: float) -> float:
	if x <= float(t[0][0]):
		return float(t[0][1])
	for i in range(1, t.size()):
		if x <= float(t[i][0]):
			var a: Array = t[i - 1]
			var b: Array = t[i]
			var f := (x - float(a[0])) / (float(b[0]) - float(a[0]))
			return lerpf(float(a[1]), float(b[1]), f)
	return float(t[t.size() - 1][1])

static func stage_for(age: float) -> String:
	if age < INFANT_MAX: return "infant"
	if age < CHILD_MAX: return "child"
	if age < ADULT_FROM: return "adolescent"
	if age < ELDER_FROM: return "adult"
	return "elder"

## Shape for a body of `age` years. Fractions are of total height. `gender` is the simulation's label and only
## nudges the shoulder/hip balance after puberty (a display choice).
static func proportions(age: float, gender: String) -> Dictionary:
	var a := maxf(age, 0.0)
	var head := table(HEAD, a)
	var leg := table(LEG, a)
	var puberty := clampf((a - 11.0) / 7.0, 0.0, 1.0)      # 0 for children, 1 by 18
	var shoulder_k := 1.0
	var hip_k := 1.0
	match gender:
		"woman":
			shoulder_k = lerpf(1.0, 0.92, puberty); hip_k = lerpf(1.0, 1.1, puberty)
		"man":
			shoulder_k = lerpf(1.0, 1.04, puberty); hip_k = lerpf(1.0, 0.95, puberty)
	var shoulder := table(SHOULDER, a) * shoulder_k
	return {
		"stage": stage_for(a), "head": head, "leg": leg, "neck": NECK,
		"torso": 1.0 - head - leg - NECK, "arm": table(ARM, a), "shoulder": shoulder,
		"hip": shoulder * 0.82 * hip_k, "girth": table(GIRTH, a),
		"stoop": clampf((a - ELDER_FROM) / 30.0, 0.0, 1.0) * 0.22,       # forward lean of the torso, radians
		"grey": clampf((a - 45.0) / 30.0, 0.0, 1.0),                     # hair greys between 45 and 75
	}
