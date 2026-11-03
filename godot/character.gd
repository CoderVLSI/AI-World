extends Node3D
## One inhabitant's animated body. Chooses a clip from the simulation-derived state (see animation_map.gd).

const AnimationMap := preload("res://animation_map.gd")

var player: AnimationPlayer
var model: Node3D
var clips := {}
var fallbacks := {}
var current_state := ""
var rest_drop := 0.0     # metres to lower the body while resting (sit clips that assume a chair)
var drop_now := 0.0
var drop_target := 0.0

func _find_player(n: Node) -> AnimationPlayer:
	if n is AnimationPlayer:
		return n
	for c in n.get_children():
		var p := _find_player(c)
		if p != null:
			return p
	return null

func setup(scene: PackedScene, entry: Dictionary, fallbacks_in: Dictionary, height_m: float, visual_scale: float) -> void:
	model = scene.instantiate()
	add_child(model)
	model.scale = Vector3.ONE * (height_m / float(entry.get("raw_height", 1.7))) * visual_scale
	rest_drop = float(entry.get("rest_drop_m", 0.0)) * visual_scale
	clips = entry.get("clips", {})
	fallbacks = fallbacks_in
	player = _find_player(model)
	if player != null:
		for clip_name in clips.values():
			if player.has_animation(str(clip_name)):
				player.get_animation(str(clip_name)).loop_mode = Animation.LOOP_LINEAR
	play_state("idle")

func _process(delta: float) -> void:
	if model != null and not is_equal_approx(drop_now, drop_target):
		drop_now = move_toward(drop_now, drop_target, delta * 1.2)
		model.position.y = -drop_now

func play_state(state: String) -> void:
	if player == null or state == current_state:
		return
	current_state = state          # remembered even if the clip is missing, so we do not retry every frame
	var clip := AnimationMap.clip_for(state, clips, fallbacks)
	drop_target = rest_drop if (state == "rest" and clips.has("rest")) else 0.0
	if clip == "" or not player.has_animation(clip):
		return
	player.play(clip, 0.25)
