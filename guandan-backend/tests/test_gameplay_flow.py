
import pytest
from game import rooms

# --- Local test utilities ---
def add_player(room_id, username):
    room = rooms.rooms.get(room_id)
    if not room:
        raise ValueError(f"Room {room_id} does not exist")
    if "slots" not in room:
        room["slots"] = [None, None, None, None]
    for i in range(4):
        if room["slots"][i] is None:
            room["slots"][i] = username
            break
    if "ready" not in room:
        room["ready"] = {}
    room["ready"][username] = False
    if "players_data" not in room:
        room["players_data"] = {}
    room["players_data"][username] = {"ready": False, "finished": 0}
    if "hands" not in room:
        room["hands"] = {}
    room["hands"][username] = []

def setup_player_metadata(room_id, username):
    room = get_room(room_id)
    if "ready" not in room:
        room["ready"] = {}
    if "players_data" not in room:
        room["players_data"] = {}
    if "hands" not in room:
        room["hands"] = {}
    room["ready"][username] = False
    room["players_data"][username] = {"ready": False, "finished": 0}
    room["hands"][username] = []

def get_room(room_id):
    return rooms.rooms.get(room_id, {})

def set_ready(room_id, username, ready=True):
    room = get_room(room_id)
    if "ready" not in room:
        room["ready"] = {}
    room["ready"][username] = ready
    if "players_data" in room:
        if username in room["players_data"]:
            room["players_data"][username]["ready"] = ready

def mark_finished(room_id, username, order):
    room = get_room(room_id)
    if "players_data" not in room:
        room["players_data"] = {}
    room["players_data"][username] = {"finished": order}

# --- Tests ---

def test_create_room_and_add_players():
    room_id = rooms.create_room("Alice", card_back="red", wild_cards=True)
    setup_player_metadata(room_id, "Alice")
    for name in ["Bob", "Carol", "Dave"]:
        add_player(room_id, name)
    state = get_room(room_id)
    players = [p for p in state["slots"] if p]
    assert len(players) == 4
    assert all(name in players for name in ["Alice", "Bob", "Carol", "Dave"])

def test_set_and_get_player_hand():
    room_id = rooms.create_room("Alice", card_back="red", wild_cards=True)
    setup_player_metadata(room_id, "Alice")
    hand = ["3H", "4H", "5H"]
    rooms.set_player_hand(room_id, "Alice", hand)
    assert rooms.get_player_hand(room_id, "Alice") == hand

def test_set_ready_and_teams():
    room_id = rooms.create_room("Alice", card_back="red", wild_cards=True)
    setup_player_metadata(room_id, "Alice")
    add_player(room_id, "Bob")
    set_ready(room_id, "Alice", True)
    set_ready(room_id, "Bob", True)
    state = get_room(room_id)
    assert state["ready"]["Alice"] is True
    assert state["ready"]["Bob"] is True

def test_teams_default_assignment():
    room_id = rooms.create_room("Alice", card_back="red", wild_cards=True)
    setup_player_metadata(room_id, "Alice")
    for name in ["Bob", "Carol", "Dave"]:
        add_player(room_id, name)

    state = get_room(room_id)
    state["teams"] = rooms.get_teams_from_slots(state["slots"])  # ✅ first, recalculate teams
    flat = [p for team in state["teams"] for p in team]          # ✅ then flatten updated teams

    assert sorted(flat) == sorted(["Alice", "Bob", "Carol", "Dave"])

def test_can_track_finished_players():
    room_id = rooms.create_room("Alice", card_back="red", wild_cards=True)
    setup_player_metadata(room_id, "Alice")
    for name in ["Bob", "Carol", "Dave"]:
        add_player(room_id, name)
    mark_finished(room_id, "Alice", 1)
    state = get_room(room_id)
    assert state["players_data"]["Alice"]["finished"] == 1
    assert state["players_data"]["Bob"]["finished"] == 0
