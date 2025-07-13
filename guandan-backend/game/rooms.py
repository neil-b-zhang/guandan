# guandan-backend/game/rooms.py

import random
import string
from .words import WORDS  # Your word list file, adjust if not using

rooms = {}

def generate_room_id():
    """Generate room code by picking 3 random words, joined by dashes, lowercase."""
    return '-'.join(random.choice(WORDS) for _ in range(3)).lower()

def create_room(username, card_back, wild_cards):
    room_id = generate_room_id()
    while room_id in rooms:
        room_id = generate_room_id()

    rooms[room_id] = {
        "settings": {
            "cardBack": card_back,
            "wildCards": wild_cards
        },
        "players": [username],
        "ready": {username: False},
        "hands": {}
    }
    print(f"[rooms.py] Room {room_id} created with settings {rooms[room_id]['settings']}")
    return room_id

def join_room(username, room_id):
    if room_id in rooms:
        if username not in rooms[room_id]["players"]:
            rooms[room_id]["players"].append(username)
            rooms[room_id]["ready"][username] = False
            print(f"[rooms.py] {username} joined room {room_id}")
        return True
    print(f"[rooms.py] Attempted to join non-existent room {room_id}")
    return False

def get_room_players(room_id):
    return rooms[room_id]["players"] if room_id in rooms else []

def set_player_ready(room_id, username, ready):
    if room_id in rooms and username in rooms[room_id]["ready"]:
        rooms[room_id]["ready"][username] = bool(ready)
        print(f"[rooms.py] {username} set ready={ready} in room {room_id}")

def all_players_ready(room_id):
    if room_id in rooms:
        return all(rooms[room_id]["ready"].values())
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
