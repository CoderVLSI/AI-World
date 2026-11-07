extends CanvasLayer
## Text overlay. Read-only: shows what the simulation publishes; sends nothing.

var top := Label.new()
var side := Label.new()
var hint := Label.new()
var bar := HSlider.new()                  # playback only: pick any recorded tick
var bar_label := Label.new()
signal scrubbed(tick: int)

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
	bar.position = Vector2(18, 652); bar.custom_minimum_size = Vector2(560, 22); bar.size = Vector2(560, 22)
	bar.step = 1.0; bar.visible = false; bar.focus_mode = Control.FOCUS_NONE
	bar.value_changed.connect(func(v: float): scrubbed.emit(int(v)))
	add_child(bar)
	bar_label.position = Vector2(592, 650); bar_label.add_theme_font_size_override("font_size", 14); bar_label.visible = false
	bar_label.add_theme_color_override("font_color", Color("#e6ede5")); bar_label.add_theme_color_override("font_shadow_color", Color(0, 0, 0, 0.8))
	add_child(bar_label)

## Playback of a finished run: a bar over the recorded ticks. Moving it only chooses which recorded moment to show.
func setup_playback(final_tick: int) -> void:
	bar.max_value = maxi(final_tick, 1); bar.visible = true; bar_label.visible = true
	if OS.has_feature("mobile"):
		hint.text = "PLAYBACK  |  drag the bar to any tick  |  drag: orbit · pinch: zoom · two fingers: pan"
		return
	hint.text = "PLAYBACK  |  space pause · ←/→ step · [ ] speed · Home/End · drag the bar  |  right-drag orbit · wheel zoom · WASD pan · click a person"

func show_playback(tick: int, final_tick: int, playing: bool, speed: float) -> void:
	bar.set_value_no_signal(tick)
	bar_label.text = "tick %d / %d   %s   %s×" % [tick, final_tick, "▶ playing" if playing else "❚❚ paused", str(speed)]

## How many living people are at least `level` thirsty / hungry (0-100 scales the simulation publishes); for the top line. Display only.
static func needs_summary(agents: Array, level: float = 50.0) -> String:
	var thirsty := 0; var hungry := 0; var hurt := 0
	for a in agents:
		if not a.get("alive", false): continue
		if float(a.get("thirst", 0)) >= level: thirsty += 1
		if float(a.get("hunger", 0)) >= level: hungry += 1
		if float(a.get("health", 100)) < level: hurt += 1
	if thirsty + hungry + hurt == 0: return ""
	var parts := []
	if thirsty > 0: parts.append("%d thirsty" % thirsty)
	if hungry > 0: parts.append("%d hungry" % hungry)
	if hurt > 0: parts.append("%d badly hurt" % hurt)
	return "   ⚠ " + ", ".join(parts) + " (≥%d)" % int(level)

## Plain names of the hazard zones currently listed, for the top line.
static func zone_summary(hazards: Array) -> String:
	var words := []
	for h in hazards:
		var w := str(h.get("phenomenon", ""))
		if w != "" and not words.has(w): words.append(w)
	return "" if words.is_empty() else "   ⚠ " + ", ".join(words)

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
	top.text += zone_summary(live.get("environment_hazards", []))
	top.text += needs_summary(live.get("agents", []))

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
