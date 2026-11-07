extends SceneTree
## Run: godot --headless --path godot --script res://tests/hud_test.gd
## The top-line needs summary counts only living people at or above the level, and says nothing when nobody is in need.
const Hud := preload("res://hud.gd")
var failures := 0

func check(cond: bool, what: String) -> void:
	if not cond:
		failures += 1; print("FAIL: ", what)

func _initialize() -> void:
	var calm := [{"alive": true, "thirst": 10, "hunger": 5, "health": 100}, {"alive": true, "thirst": 49.9, "hunger": 0, "health": 51}]
	check(Hud.needs_summary(calm) == "", "nobody at the level: nothing shown")
	var people := [{"alive": true, "thirst": 50, "hunger": 10, "health": 100}, {"alive": true, "thirst": 80, "hunger": 60, "health": 40},
		{"alive": false, "thirst": 99, "hunger": 99, "health": 0}, {"alive": true, "thirst": 20, "hunger": 70, "health": 100}]
	var s := Hud.needs_summary(people)
	check(s.contains("2 thirsty") and s.contains("2 hungry") and s.contains("1 badly hurt"), "counts living people only (got %s)" % s)
	check(Hud.needs_summary([]) == "" and Hud.needs_summary([{"alive": true}]) == "", "missing fields are treated as fine")
	check(Hud.needs_summary(people, 75.0).contains("1 thirsty") and not Hud.needs_summary(people, 75.0).contains("hungry"), "the level is respected")
	print("hud tests: ", "ok" if failures == 0 else "FAILED")
	quit(1 if failures > 0 else 0)
