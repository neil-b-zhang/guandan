# guandan-backend/game/rooms.py

import random
import string
from .words import WORDS  # If you use word-based room IDs

rooms = {}

def generate_room_id():
    # For testing: return 'test'
    #return '-'.join(random.choice(WORDS) for _ in range(3)).lower()
    return 'test'

def initial_slots():
    return [None, None, None, None]

def create_room(username, card_back, wild_cards):
    room_id = generate_room_id()
    while room_id in rooms:
        room_id = generate_room_id()
    slots = initial_slots()
    slots[0] = username  # host always gets slot 0 by default
    rooms[room_id] = {
        "settings": {
            "cardBack": card_back,
            "wildCards": wild_cards,
            "trumpSuit": "hearts",
            "startingLevels": ["2", "2", "2", "2"]
        },
        "slots": slots,  # always 4 slots
        "ready": {username: False},
        "hands": {},
        "levels": {},
        "teams": get_teams_from_slots(slots)
    }
    print(f"[rooms.py] Room {room_id} created with slots {slots} and settings {rooms[room_id]['settings']}")
    return room_id

def join_room(username, room_id):
    if room_id not in rooms:
        print(f"[rooms.py] Attempted to join non-existent room {room_id}")
        return False
    slots = rooms[room_id]["slots"]
    if username in slots:
        return True  # already in a slot
    for i in range(4):
        if not slots[i]:
            slots[i] = username
            rooms[room_id]["ready"][username] = False
            rooms[room_id]["teams"] = get_teams_from_slots(slots)
            print(f"[rooms.py] {username} joined room {room_id} at slot {i}")
            return True
    print(f"[rooms.py] Room {room_id} full")
    return False

def get_teams_from_slots(slots):
    # slots[0] and [2] = Team A, [1] and [3] = Team B
    teamA = [p for i, p in enumerate(slots) if p and i % 2 == 0]
    teamB = [p for i, p in enumerate(slots) if p and i % 2 == 1]
    return [teamA, teamB]

def get_room_players(room_id):
    if room_id in rooms:
        return [p for p in rooms[room_id]["slots"] if p]
    return []

def set_player_ready(room_id, username, ready):
    if room_id in rooms:
        rooms[room_id]["ready"][username] = bool(ready)
        print(f"[rooms.py] {username} set ready={ready} in room {room_id}")

def all_players_ready(room_id):
    if room_id in rooms:
        slots = rooms[room_id]["slots"]
        players = [p for p in slots if p]
        ready = rooms[room_id]["ready"]
        #return all(ready.get(p, False) for p in players) and len(players) == 4
        return all(ready.get(p, False) for p in players) and len(players) >= 2

    return False

def get_ready_states(room_id):
    if room_id in rooms:
        return rooms[room_id]["ready"]
    return {}

def set_player_hand(room_id, username, hand):
    if room_id in rooms:
        rooms[room_id].setdefault('hands', {})
        rooms[room_id]['hands'][username] = hand

def get_player_hand(room_id, username):
    if room_id in rooms and 'hands' in rooms[room_id]:
        return rooms[room_id]['hands'].get(username, [])
    return []

# Extra: utility for moving seats (used by app.py)
def move_seat(room_id, username, slot_idx):
    if room_id not in rooms: return False
    slots = rooms[room_id]["slots"]
    if slots[slot_idx]:
        return False
    for i in range(4):
        if slots[i] == username:
            slots[i] = None
    slots[slot_idx] = username
    rooms[room_id]["teams"] = get_teams_from_slots(slots)
    return True
