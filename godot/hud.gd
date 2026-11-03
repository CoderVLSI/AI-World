extends CanvasLayer
## Text overlay. Read-only: shows what the simulation publishes; sends nothing.

var top := Label.new()
var side := Label.new()
var hint := Label.new()

func _ready() -> void:
	for l in [top, side, hint]:
		l.add_theme_color_override("font_color", Color("#e6ede5")); l.add_theme_color_override("font_shadow_color", Color(0, 0, 0, 0.8))
		l.add_theme_constant_override("shadow_offset_x", 1); l.add_theme_constant_override("shadow_offset_y", 1)
		add_child(l)
	top.position = Vector2(18, 12); top.add_theme_font_size_override("font_size", 18)
	side.position = Vector2(18, 70); side.add_theme_font_size_override("font_size", 15)
	hint.text = "READ-ONLY WITNESS  |  right-drag orbit · wheel zoom · WASD / shift+drag pan · click a person to inspect · F focus people"
	hint.add_theme_font_size_override("font_size", 13); hint.modulate = Color(1, 1, 1, 0.7)
	hint.position = Vector2(18, 690)
	top.text = "Connecting…"

func show_live(live: Dictionary, connected: bool) -> void:
	if not connected:
		top.text = "DISCONNECTED — waiting for the simulation server"; return
	var c: Dictionary = live.get("climate", {}) if live.get("climate") != null else {}
	var alive := 0
	for a in live.get("agents", []):
		if a.get("alive", false): alive += 1
	var animals := int(live.get("wildlife", {}).get("animals", []).size()) if live.has("wildlife") else 0
	var hour := float(c.get("hour", 0.0))
	top.text = "CAITANYA   tick %d   day %d %02d:%02d   %s %s %s°C   %d alive%s" % [
		int(live.tick), int(c.get("day", 0)), int(hour), int((hour - floor(hour)) * 60.0), str(c.get("season", "")),
		str(c.get("weather", "")), str(c.get("temperature_c", "")), alive, ("   %d animals" % animals) if animals > 0 else ""]

func show_selected(a) -> void:
	if a == null:
		side.text = ""; return
	var s := "%s\n%s · %s · generation %d\nage %.1f   height %d cm\nhunger %d   thirst %d\nenergy %d   health %d%s\n" % [
		a.id, a.get("gender", ""), a.get("life_stage", ""), int(a.get("generation", 0)), float(a.get("age_years", 0.0)),
		int(a.get("height_cm", 0)), int(a.hunger), int(a.thirst), int(a.energy), int(a.health), "   UNWELL" if a.get("unwell", false) else ""]
	var la = a.get("last_action")
	s += "last recorded action: %s\n" % ("none" if la == null else "%s (tick %d, %s)" % [la.type, int(la.tick), str(la.origin)])
	if a.has("task"):
		var t: Dictionary = a.task
		s += "plan: %s %s\n  chosen by %s, %d steps left" % [t.kind, JSON.stringify(t.params), str(t.chosen_by), int(t.steps_left)]
	else:
		s += "plan: none (acts when asked)"
	side.text = s
