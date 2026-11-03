extends SceneTree
## Run: godot --headless --path godot --script res://tests/bubble_test.gd
## Speech bubbles: spoken lines appear above the speaker, thoughts only as "...", capped, expiring, repeatable-safe.
const Actors := preload("res://actors.gd")
var failures := 0

class StubTerrain extends RefCounted:
	const HEIGHT_SCALE := 1.0
	func height_at(_x: float, _z: float) -> float:
		return 0.0

func check(cond: bool, what: String) -> void:
	if not cond:
		failures += 1; print("FAIL: ", what)

func _initialize() -> void:
	var root := Node3D.new(); get_root().add_child(root)
	var cam := Camera3D.new(); root.add_child(cam); cam.current = true
	cam.transform = Transform3D(Basis.looking_at(Vector3(0, -0.4, -1)), Vector3(20, 10, 40))
	var actors := Actors.new(); root.add_child(actors)
	var agents := []
	for i in 40:
		agents.append({"id": "agent-%04d" % i, "x": 10 + (i % 8) * 2, "z": 10 + (i / 8) * 2, "alive": true, "gender": "man", "age_years": 30.0,
			"height_cm": 170.0, "skin_tone": "#bd8c68", "clothing_color": "#678b91", "last_action": null})
	var live := {"tick": 5, "agents": agents, "resources": [], "objects": [], "speech": []}
	await process_frame
	actors.update_live(live, StubTerrain.new())
	await process_frame
	check(actors.bubbles_shown().is_empty(), "no speech, no bubbles")
	# a spoken line and a thought
	live.speech = [{"agent_id": "agent-0001", "tick": 5, "kind": "speech", "text": "Good morning, friend."},
		{"agent_id": "agent-0002", "tick": 5, "kind": "thought", "text": null}]
	actors.update_live(live, StubTerrain.new())
	await process_frame; await process_frame
	var shown := actors.bubbles_shown()
	check(shown.size() == 2, "two bubbles (got %d)" % shown.size())
	for b in shown:
		if b.id == "agent-0001":
			check(b.text == "Good morning, friend." and b.kind == "speech", "the spoken line is shown")
		else:
			check(b.kind == "thought" and b.text == "…", "a thought shows only an ellipsis")
	# a bubble sits above its speaker's head, never inside the body
	var person: Node3D = actors.people["agent-0001"]
	var bubble: Node3D = actors._bubble_pool[0] if actors._bubble_pool[0].get_meta("agent", "") == "agent-0001" else actors._bubble_pool[1]
	check(bubble.position.y > person.position.y + float(person.top_y()), "the bubble is above the head")
	# the same line seen again in the next poll does not restart or duplicate it
	actors.update_live(live, StubTerrain.new()); await process_frame
	check(actors.bubbles_shown().size() == 2, "a repeated poll does not duplicate bubbles")
	# long text is truncated
	live.speech = [{"agent_id": "agent-0003", "tick": 6, "kind": "speech", "text": "w".repeat(500)}]
	actors.update_live(live, StubTerrain.new()); await process_frame
	var long_text := ""
	for b in actors.bubbles_shown():
		if b.id == "agent-0003": long_text = b.text
	check(long_text.length() == Actors.BUBBLE_MAX_CHARS and long_text.ends_with("…"), "long speech is truncated for the bubble")
	# never more than the pool allows, nearest first
	live.speech = []
	for i in 40:
		live.speech.append({"agent_id": "agent-%04d" % i, "tick": 7, "kind": "speech", "text": "line %d" % i})
	actors.update_live(live, StubTerrain.new()); await process_frame
	check(actors.bubbles_shown().size() == Actors.MAX_BUBBLES, "at most %d bubbles at once (got %d)" % [Actors.MAX_BUBBLES, actors.bubbles_shown().size()])
	# toggling off hides them all
	actors.bubbles_on = false; await process_frame
	check(actors.bubbles_shown().is_empty(), "bubbles can be switched off")
	actors.bubbles_on = true
	# bubbles expire
	actors.bubble_seconds_override = 0.3
	live.speech = [{"agent_id": "agent-0005", "tick": 8, "kind": "speech", "text": "short lived"}]
	actors._speech.clear()
	actors.update_live(live, StubTerrain.new()); await process_frame
	check(actors.bubbles_shown().size() == 1, "a fresh line appears")
	await create_timer(0.6).timeout; await process_frame
	check(actors.bubbles_shown().is_empty(), "and expires")
	# far away speakers are not drawn
	cam.transform = Transform3D(Basis.looking_at(Vector3(0, -1, 0), Vector3.FORWARD), Vector3(900, 300, 900))
	actors.bubble_seconds_override = 5.0
	live.speech = [{"agent_id": "agent-0006", "tick": 9, "kind": "speech", "text": "too far to read"}]
	actors.update_live(live, StubTerrain.new()); await process_frame
	check(actors.bubbles_shown().is_empty(), "speakers beyond the range get no bubble")
	# a speaker who is not in the world (left, or unknown) is ignored without error
	cam.transform = Transform3D(Basis.looking_at(Vector3(0, -0.4, -1)), Vector3(20, 10, 40))
	actors._speech.clear()
	live.speech = [{"agent_id": "agent-9999", "tick": 10, "kind": "speech", "text": "ghost"}]
	actors.update_live(live, StubTerrain.new()); await process_frame
	check(actors.bubbles_shown().is_empty(), "an unknown speaker is ignored")
	print("bubble tests: ", "FAILED" if failures > 0 else "ok")
	quit(1 if failures > 0 else 0)
