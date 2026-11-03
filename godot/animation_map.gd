extends RefCounted
## Which animation state an inhabitant is in. The rule: a state may only come from something the simulation
## actually RECORDED (a validated action, or real movement). Nothing is invented: there is no running, fighting
## or hunting state because the simulation has no such actions yet. Unknown actions fall back to idle.

const RECENT_TICKS := 4

# Event types as published by the engine (lower-case action names). "reflect" is shown as a neutral seated
# pose; the viewer deliberately does not label it (or any state) with a spiritual meaning.
const ACTION_STATES := {
	"rest": "rest", "rest_for": "rest", "reflect": "rest",
	"speak": "talk", "teach": "talk", "share_knowledge": "talk",
	"gather": "work", "gather_at": "work", "gather_with": "work", "pick": "work", "take": "work", "drop": "work",
	"stow": "work", "inspect": "work", "strike": "work", "combine": "work", "separate": "work", "heat": "work",
	"cool": "work", "rub": "work", "feed_fire": "work", "test": "work", "place": "work", "write": "work",
	"revise": "work", "read": "work", "care": "work", "give": "work", "hand_over": "work", "write_findings": "work",
	"eat": "eat", "drink": "eat",
}
const MOVE_ACTIONS := ["move"]

static func state_for(last_action, tick: int, moving: bool) -> String:
	if moving:
		return "walk"
	if last_action == null or typeof(last_action) != TYPE_DICTIONARY:
		return "idle"
	if tick - int(last_action.get("tick", -1000)) > RECENT_TICKS:
		return "idle"
	var kind := str(last_action.get("type", ""))
	if kind in MOVE_ACTIONS:
		return "walk"
	return ACTION_STATES.get(kind, "idle")

static func clip_for(state: String, clips: Dictionary, fallbacks: Dictionary) -> String:
	if clips.has(state):
		return str(clips[state])
	var fb := str(fallbacks.get(state, "idle"))
	return str(clips.get(fb, clips.get("idle", "")))
