extends Node
## Campaign flow: intro → briefing → playing → clear → …

enum State { INTRO, BRIEFING, PLAYING, CLEAR, PAUSED, GAME_OVER, WIN }

signal state_changed(old_state: State, new_state: State)
signal sector_started(sector_index: int)
signal sector_cleared(sector_index: int)

var state: State = State.INTRO
var _pre_pause: State = State.PLAYING
var active_sector: int = 0


func _ready() -> void:
	# Vertical slice starts at The Fringe briefing.
	active_sector = 0
	var story = get_node_or_null("/root/StoryDB")
	if story:
		story.current_sector = active_sector


func set_state(new_state: State) -> void:
	if state == new_state:
		return
	var old := state
	state = new_state
	# Pause tree only for pause menu — briefing/clear keep processing input on UI.
	get_tree().paused = state == State.PAUSED
	state_changed.emit(old, new_state)


func begin_campaign(sector_index: int = 0) -> void:
	active_sector = sector_index
	var story = get_node_or_null("/root/StoryDB")
	if story:
		story.current_sector = active_sector
	set_state(State.BRIEFING)
	sector_started.emit(active_sector)


func advance_from_briefing() -> void:
	if state == State.BRIEFING:
		set_state(State.PLAYING)


func notify_sector_cleared() -> void:
	if state != State.PLAYING:
		return
	var save = get_node_or_null("/root/SaveGame")
	if save and not (active_sector in save.sectors_cleared):
		save.sectors_cleared.append(active_sector)
		save.grant_scrap(20)
		save.write()
	sector_cleared.emit(active_sector)
	set_state(State.CLEAR)


func advance_from_clear() -> void:
	if state != State.CLEAR:
		return
	# Slice: after Fringe clear, show win beat (full map later).
	set_state(State.WIN)


func toggle_pause() -> void:
	if state == State.PAUSED:
		set_state(_pre_pause)
	elif state == State.PLAYING:
		_pre_pause = state
		set_state(State.PAUSED)


func notify_player_died() -> void:
	set_state(State.GAME_OVER)


func notify_win() -> void:
	set_state(State.WIN)


func combat_enabled() -> bool:
	return state == State.PLAYING
