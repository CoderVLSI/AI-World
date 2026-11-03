extends SceneTree
## Run: godot --headless --path godot --script res://tests/animation_map_test.gd
const AnimationMap := preload("res://animation_map.gd")
var failures := 0

func check(cond: bool, what: String) -> void:
	if not cond:
		failures += 1; print("FAIL: ", what)

func _init() -> void:
	var a := AnimationMap
	check(a.state_for(null, 10, false) == "idle", "no recorded action -> idle (never invented)")
	check(a.state_for(null, 10, true) == "walk", "real movement -> walk")
	check(a.state_for({"type": "rest", "tick": 9}, 10, false) == "rest", "recent rest -> rest")
	check(a.state_for({"type": "rest", "tick": 1}, 10, false) == "idle", "stale rest -> idle")
	check(a.state_for({"type": "speak", "tick": 10}, 10, false) == "talk", "speak -> talk")
	check(a.state_for({"type": "gather", "tick": 10}, 10, false) == "work", "gather -> work")
	check(a.state_for({"type": "strike", "tick": 10}, 10, false) == "work", "strike (experiment) -> work, not fight")
	check(a.state_for({"type": "eat", "tick": 10}, 10, false) == "eat", "eat -> eat")
	check(a.state_for({"type": "move", "tick": 10}, 10, false) == "walk", "recent move -> walk")
	check(a.state_for({"type": "no_such_action", "tick": 10}, 10, false) == "idle", "unknown action -> idle")
	check(a.state_for({"type": "rest", "tick": 10}, 10, true) == "walk", "moving wins over a stale pose")
	var allowed := ["idle", "walk", "rest", "talk", "work", "eat"]
	for kind in a.ACTION_STATES:
		check(a.ACTION_STATES[kind] in allowed, "every mapped state is a known state: " + kind)
		check(not ("fight" in a.ACTION_STATES[kind] or "hunt" in a.ACTION_STATES[kind] or "run" == a.ACTION_STATES[kind]), "no invented violence/hunting/running state")
	var fall := {"rest": "idle", "talk": "idle", "work": "idle", "eat": "idle", "walk": "idle"}
	check(a.clip_for("rest", {"idle": "idle", "rest": "sit_idle"}, fall) == "sit_idle", "model with a rest clip uses it")
	check(a.clip_for("rest", {"idle": "idle"}, fall) == "idle", "model without a rest clip falls back to idle")
	check(a.clip_for("talk", {"idle": "stand"}, fall) == "stand", "fallback uses the model's own idle clip name")
	print("ANIMATION MAP TESTS: ", "PASS" if failures == 0 else "FAILED (%d)" % failures)
	quit(0 if failures == 0 else 1)
