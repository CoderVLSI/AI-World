extends CanvasLayer
## Asks for the address of a witness server. A phone has no command-line options, so the app asks (and remembers the last address).
## Read-only: this only chooses where the viewer sends its GET requests; it sends nothing else.
signal submitted(url: String)
signal opened

const CONFIG := "user://server.cfg"
const DEFAULT_PORT := ":8000"

var panel := PanelContainer.new()
var edit := LineEdit.new()
var status := Label.new()
var change_button := Button.new()      # small button that reopens the panel once connected

## "100.64.0.5" -> "http://100.64.0.5:8000"; keeps an explicit scheme, port and path; "" when it cannot be an address.
static func normalize(text: String) -> String:
	var t := text.strip_edges()
	if t == "" or t.contains(" "):
		return ""
	if not (t.begins_with("http://") or t.begins_with("https://")):
		t = "http://" + t
	t = t.rstrip("/")
	var rest := t.substr(t.find("://") + 3)
	var host := rest.split("/")[0]
	if host == "" or host.begins_with(":") or host.ends_with(":"):
		return ""
	if not host.contains(":") and t.begins_with("http://"):
		t = t.replace(host, host + DEFAULT_PORT)
	return t

static func load_saved() -> String:
	var cfg := ConfigFile.new()
	if cfg.load(CONFIG) != OK:
		return ""
	return str(cfg.get_value("server", "url", ""))

static func save(url: String) -> void:
	var cfg := ConfigFile.new()
	cfg.set_value("server", "url", url)
	cfg.save(CONFIG)

func _ready() -> void:
	layer = 20
	panel.set_anchors_preset(Control.PRESET_CENTER)
	panel.custom_minimum_size = Vector2(760, 0)
	panel.grow_horizontal = Control.GROW_DIRECTION_BOTH; panel.grow_vertical = Control.GROW_DIRECTION_BOTH
	var box := VBoxContainer.new(); box.add_theme_constant_override("separation", 14)
	var title := Label.new(); title.text = "CAITANYA Witness"; title.add_theme_font_size_override("font_size", 40)
	var help := Label.new(); help.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	help.text = "Address of the simulation server (this app only watches: it reads, it never sends anything to the world)."
	help.add_theme_font_size_override("font_size", 24)
	edit.placeholder_text = "100.64.0.5:8000"; edit.add_theme_font_size_override("font_size", 32); edit.custom_minimum_size = Vector2(0, 64)
	edit.text_submitted.connect(func(_t): _submit())
	var go := Button.new(); go.text = "Connect"; go.add_theme_font_size_override("font_size", 32); go.custom_minimum_size = Vector2(0, 72)
	go.pressed.connect(_submit)
	status.add_theme_font_size_override("font_size", 22); status.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	for n in [title, help, edit, go, status]:
		box.add_child(n)
	panel.add_child(box); add_child(panel)
	change_button.text = "server"; change_button.add_theme_font_size_override("font_size", 22)
	change_button.set_anchors_preset(Control.PRESET_TOP_RIGHT); change_button.position = Vector2(-120, 8)
	change_button.pressed.connect(func(): open(edit.text))
	change_button.visible = false
	add_child(change_button)
	panel.visible = false

func open(prefill: String = "") -> void:
	edit.text = prefill; status.text = ""
	panel.visible = true; change_button.visible = false
	opened.emit()

func _submit() -> void:
	var url := normalize(edit.text)
	if url == "":
		status.text = "Enter an address like 100.64.0.5:8000"
		return
	save(url)
	panel.visible = false; change_button.visible = true
	submitted.emit(url)
