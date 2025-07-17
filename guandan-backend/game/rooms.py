# guandan-backend/game/rooms.py

import random
import string
from .words import WORDS  # If you use word-based room IDs

rooms = {}

def generate_room_id():
    # Try to find a unique ID with no repeated words
    for _ in range(10):
        parts = random.sample(WORDS, 3)  # ensures all 3 words are unique
        room_id = '-'.join(parts).lower()
        if room_id not in rooms:
            return room_id

    # Fallback: random string if uniqueness fails
    return ''.join(random.choices(string.ascii_lowercase, k=8))
    #return 'test'  # For testing
    
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
            "startingLevels": ["2", "2", "2", "2"],
            "showCardCount": False
        },
        "slots": slots,
        "ready": {username: False},
        "hands": {},
        "levels": {},
        "teams": get_teams_from_slots(slots),
        "sids": {}  # ✅ Track session IDs for tribute handling
    }
    print(f"[rooms.py] Room {room_id} created with slots {slots} and settings {rooms[room_id]['settings']}")
    return room_id

def join_room(username, room_id):
    if room_id not in rooms:
        print(f"[rooms.py] Attempted to join non-existent room {room_id}")
        return False
    slots = rooms[room_id]["slots"]
    if username in slots:
        return True
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

def move_seat(room_id, username, slot_idx):
    if room_id not in rooms:
        return False
    slots = rooms[room_id]["slots"]
    if slots[slot_idx]:
        return False
    for i in range(4):
        if slots[i] == username:
            slots[i] = None
    slots[slot_idx] = username
    rooms[room_id]["teams"] = get_teams_from_slots(slots)
    return True

# ✅ Register a user's Socket.IO session ID for direct messaging
def register_sid(room_id, username, sid):
    if room_id in rooms:
        rooms[room_id].setdefault("sids", {})[username] = sid

# ✅ Optional: retrieve a sid
def get_sid(room_id, username):
    return rooms.get(room_id, {}).get("sids", {}).get(username)
