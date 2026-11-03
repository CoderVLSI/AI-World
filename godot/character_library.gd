extends RefCounted
## Loads the character models listed in assets/manifest.json when they have been fetched and imported.
## When they are missing, `available` stays false and the viewer keeps its simple figures.

const Character := preload("res://character.gd")

var manifest := {}
var scenes := {}
var available := false

func _init() -> void:
	var f := FileAccess.open("res://assets/manifest.json", FileAccess.READ)
	if f == null:
		return
	var parsed = JSON.parse_string(f.get_as_text())
	if typeof(parsed) != TYPE_DICTIONARY:
		return
	manifest = parsed
	for id in manifest.get("characters", {}):
		var path := "res://assets/" + str(manifest.characters[id].file)
		if ResourceLoader.exists(path):
			scenes[id] = load(path)
	available = not scenes.is_empty()

## Which body to show. A display choice only: the simulation's gender label picks the model; anything else
## (nonbinary, unspecified children) alternates by agent number so no one model is assigned to a category.
func pick(agent: Dictionary) -> String:
	var wanted := ""
	match str(agent.get("gender", "")):
		"woman": wanted = "woman"
		"man": wanted = "man"
		_:
			var digits := str(agent.get("id", "0")).get_slice("-", 1)
			wanted = "woman" if int(digits) % 2 == 0 else "man"
	for id in scenes:
		if str(manifest.characters[id].get("role", "")) == wanted:
			return id
	return scenes.keys()[0] if not scenes.is_empty() else ""

func make(agent: Dictionary, visual_scale: float) -> Node3D:
	var id := pick(agent)
	if id == "":
		return null
	var body := Character.new()
	body.setup(scenes[id], manifest.characters[id], manifest.get("state_fallbacks", {}),
		float(agent.get("height_cm", 170)) / 100.0, visual_scale)
	return body
