from flask import Flask, jsonify, request
from flask_socketio import SocketIO, emit, join_room as sio_join_room
from game.rooms import (
    create_room,
    join_room as join_existing_room,
    get_room_players,
    set_player_ready,
    all_players_ready,
    get_ready_states,
    set_player_hand,
    get_player_hand,
    rooms,
    generate_room_id
)
from game.deck import create_deck, shuffle_deck, deal_cards
from game.hands import hand_type, beats, find_wilds

LEVEL_SEQUENCE = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
SUIT_OPTIONS = ['hearts', 'spades', 'diamonds', 'clubs']

def get_next_level(current, up):
    i = LEVEL_SEQUENCE.index(current)
    i = min(i + up, len(LEVEL_SEQUENCE) - 1)
    return LEVEL_SEQUENCE[i]

def initial_slots():
    return [None, None, None, None]

def fill_slot(slots, username):
    for i in range(4):
        if not slots[i]:
            slots[i] = username
            return i
    return -1

def get_teams_from_slots(slots):
    teamA = [p for i, p in enumerate(slots) if p and i % 2 == 0]
    teamB = [p for i, p in enumerate(slots) if p and i % 2 == 1]
    return [teamA, teamB]

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

@app.route("/")
def index():
    return jsonify({"status": "Guandan backend running"})

@socketio.on('create_room')
def handle_create_room(data):
    username = data.get('username')
    room_name = data.get('roomName', '')  # Optional from frontend
    card_back = data.get('cardBack', 'red')
    wild_cards = data.get('wildCards', True)
    trump_suit = data.get('trumpSuit', 'hearts')
    starting_levels = data.get('startingLevels', ["2", "2", "2", "2"])

    if not username:
        emit('error_msg', "Username required.", room=request.sid)
        return

    # Use user-supplied lobby name if present, otherwise generate one
    if room_name:
        # Sanitize: lowercase, replace spaces with dashes
        room_id = room_name.strip().lower().replace(" ", "-")
    else:
        room_id = generate_room_id()

    # Check for existing room
    if room_id in rooms:
        emit('error_msg', "Game lobby already exists with that name", room=request.sid)
        return

    # Optionally check if username is already in use in another room
    for existing in rooms.values():
        if username in existing.get("players", []):
            emit('error_msg', f"Username '{username}' already exists in another room.", room=request.sid)
            return

    # --- Create the new room with slot 0 assigned to creator ---
    rooms[room_id] = {
        "settings": {
            "cardBack": card_back,
            "wildCards": wild_cards,
            "trumpSuit": trump_suit,
            "startingLevels": starting_levels
        },
        "players": [username],
        "slots": [username, None, None, None],
        "ready": {username: False},
        "hands": {},
        "connected_sids": set([request.sid])   
}
    print(f"[rooms.py] Room {room_id} created with settings {rooms[room_id]['settings']}")

    sio_join_room(room_id)
    rooms[room_id].setdefault("connected_sids", set()).add(request.sid)

    emit('room_joined', {
        "roomId": room_id,
        "username": username,
        "players": [username],
        "slots": rooms[room_id]["slots"],
        "settings": rooms[room_id]["settings"]
    }, room=request.sid)


@socketio.on('join_room')
def handle_join_room(data):
    username = data.get('username')
    room_id = data.get('roomId', '').lower()
    if not username or not room_id:
        emit('error_msg', "Username and Room ID required", room=request.sid)
        return

    if room_id not in rooms:
        emit('error_msg', "Room does not exist", room=request.sid)
        return

    slots = rooms[room_id].get("slots")
    if not slots:
        slots = initial_slots()
        rooms[room_id]["slots"] = slots
    if username in slots:
        seat_idx = slots.index(username)
    else:
        seat_idx = fill_slot(slots, username)
    if seat_idx == -1:
        emit('error_msg', "Room is full.", room=request.sid)
        return

    sio_join_room(room_id)
    rooms[room_id]["teams"] = get_teams_from_slots(slots)

    emit('room_joined', {
        "roomId": room_id,
        "username": username,
        "players": [u for u in slots if u],
        "settings": rooms[room_id]["settings"],
        "levels": rooms[room_id].get("levels", {}),
        "teams": rooms[room_id]["teams"],
        "slots": rooms[room_id]["slots"]
    }, room=request.sid)
    broadcast_room_update(room_id)

@socketio.on('move_seat')
def handle_move_seat(data):
    username = data.get('username')
    room_id = data.get('roomId')
    slot_idx = data.get('slotIdx')
    if not username or room_id not in rooms or slot_idx is None:
        return
    slots = rooms[room_id]["slots"]
    if slots[slot_idx]:
        emit('error_msg', "Seat already taken.", room=request.sid)
        return
    # Remove user from previous slot, if any
    for i in range(4):
        if slots[i] == username:
            slots[i] = None
    # Assign to new slot
    slots[slot_idx] = username
    rooms[room_id]["slots"] = slots
    # Update teams based on slot arrangement
    rooms[room_id]["teams"] = get_teams_from_slots(slots)
    # Broadcast updated room state to all players in the room
    broadcast_room_update(room_id)


@socketio.on('update_room_settings')
def handle_update_room_settings(data):
    room_id = data.get('roomId')
    new_settings = data.get('settings', {})
    if room_id not in rooms:
        return
    for k in ["wildCards", "cardBack", "trumpSuit", "startingLevels", "showCardCount"]:
        if k in new_settings:
            rooms[room_id]["settings"][k] = new_settings[k]
    broadcast_room_update(room_id)

def broadcast_room_update(room_id):
    """Emit the full current lobby state to all users in the room."""
    if room_id not in rooms:
        return
    room = rooms[room_id]
    emit('room_update', {
        "roomId": room_id,
        "players": room.get("players", []),
        "slots": room.get("slots", [None, None, None, None]),
        "readyStates": room.get("ready", {}),
        "settings": room.get("settings", {}),
        "teams": room.get("teams", [[], []]),  # If you support teams
        "levels": room.get("levels", {}),      # If you track per-player/team levels
        "startingLevels": room["settings"].get("startingLevels", ["2","2","2","2"])
        # Add any other state you want the frontend to keep in sync
    }, room=room_id)

@socketio.on('set_ready')
def handle_set_ready(data):
    room_id = data.get('roomId')
    username = data.get('username')
    ready = data.get('ready', False)
    set_player_ready(room_id, username, ready)
    broadcast_room_update(room_id)

@socketio.on('start_game')
def handle_start_game(data):
    room_id = data.get('roomId')
    username = data.get('username')
    if not all_players_ready(room_id):
        emit('error_msg', "Not all players are ready!", room=request.sid)
        return
    # Determine trump/level for new round: use the winning team's level if present,
    # otherwise use starting levels from settings.
    start_new_game_round(room_id)

def start_new_game_round(room_id):
    slots = rooms[room_id]["slots"]
    players = [u for u in slots if u]
    deck = create_deck()
    shuffle_deck(deck)
    hands = deal_cards(deck, len(players))
    for player, hand in zip(players, hands):
        set_player_hand(room_id, player, hand)
    # If we just finished a hand, levels were already advanced
    starting_levels = rooms[room_id]["settings"].get("startingLevels", ["2","2","2","2"])
    levels = rooms[room_id].get("levels", {})
    # If no levels exist, assign starting levels:
    if not levels or any(lv not in LEVEL_SEQUENCE for lv in levels.values()):
        levels = {}
        for i, player in enumerate(slots):
            if player:
                levels[player] = starting_levels[i]
    rooms[room_id]["levels"] = levels
    rooms[room_id]["teams"] = get_teams_from_slots(slots)
    settings = rooms[room_id].get("settings", {})
    # Determine current round's level: leading team determines the level
    teams = rooms[room_id]["teams"]
    # Default: team A is leading if just started
    winning_team = teams[0] if "winning_team" not in rooms[room_id] else rooms[room_id]["winning_team"]
    # Set current round levelRank as the minimum of winning team's levels (per classic rules)
    team_lvls = [levels[p] for p in winning_team]
    current_level = min(team_lvls, key=lambda lv: LEVEL_SEQUENCE.index(lv))
    trump_suit = settings.get("trumpSuit", "hearts")
    wild_cards = settings.get("wildCards", True)
    rooms[room_id]['game'] = {
        'players': players,
        'turn_index': 0,
        'current_play': None,
        'round_active': True,
        'passes': set(),
        'current_winner': None,
        'finish_order': [],
        'trumpSuit': trump_suit,
        'levelRank': current_level,
        'wildCards': wild_cards,
        'startingLevels': starting_levels
    }
    emit('game_started', {
        "roomId": room_id,
        "current_player": players[0],
        "levels": levels,
        "teams": rooms[room_id]["teams"],
        "slots": slots,
        "settings": settings,
        "trumpSuit": trump_suit,
        "levelRank": current_level,
        "wildCards": wild_cards,
        "startingLevels": starting_levels,
        "hands": {p: rooms[room_id]['hands'][p] for p in players}
    }, room=room_id)
    broadcast_room_update(room_id)
    for player in players:
        hand = get_player_hand(room_id, player)
        emit('deal_hand', {"hand": hand, "username": player}, room=room_id)

def start_new_trick(room_id, winner_username):
    game = rooms[room_id]['game']
    game['turn_index'] = game['players'].index(winner_username)
    game['current_play'] = None
    game['passes'] = set()
    game['current_winner'] = winner_username
    emit('game_update', {
        'current_play': None,
        'last_play_type': None,
        'hands': rooms[room_id]['hands'],
        'current_player': winner_username,
        'can_end_round': False,
        'passed_players': [],
        'levels': rooms[room_id]["levels"],
        'teams': rooms[room_id]["teams"],
        'slots': rooms[room_id]["slots"],
        'trumpSuit': game.get("trumpSuit"),
        'levelRank': game.get("levelRank"),
        'wildCards': game.get("wildCards"),
        'startingLevels': game.get("startingLevels")
    }, room=room_id)

@socketio.on('play_cards')
def handle_play_cards(data):
    room_id = data.get('roomId')
    username = data.get('username')
    cards = data.get('cards', [])

    game = rooms[room_id].get('game')
    if not game:
        emit('error_msg', "Game not active.", room=request.sid)
        return

    current_player = game['players'][game['turn_index']]
    if username != current_player:
        emit('error_msg', "Not your turn!", room=request.sid)
        return

    player_hand = rooms[room_id]['hands'][username]

    this_type = hand_type(
        cards,
        level_rank=game.get('levelRank'),
        trump_suit=game.get('trumpSuit'),
        wild_cards_enabled=game.get('wildCards')
    )
    if not this_type:
        emit('error_msg', "Invalid hand type!", room=request.sid)
        return

    last_play = game['current_play']
    if last_play and last_play['cards']:
        if not beats(
            last_play,
            {'player': username, 'cards': cards},
            level_rank=game.get('levelRank'),
            trump_suit=game.get('trumpSuit'),
            wild_cards_enabled=game.get('wildCards')
        ):
            emit('error_msg', "Your play must beat the previous hand.", room=request.sid)
            return

    for card in cards:
        if card in player_hand:
            player_hand.remove(card)
        else:
            wilds = find_wilds(
                player_hand,
                game.get('levelRank'),
                game.get('trumpSuit'),
                game.get('wildCards')
            )
            for w in wilds:
                if w in player_hand:
                    player_hand.remove(w)
                    break

    if len(player_hand) == 0:
        game['finish_order'].append(username)
        remaining_players = [p for p in game['players'] if len(rooms[room_id]['hands'][p]) > 0]
        if len(remaining_players) == 1:
            game['finish_order'].append(remaining_players[0])
            teams = rooms[room_id]["teams"]
            teamA, teamB = teams
            first = game['finish_order'][0]
            team_winners = teamA if first in teamA else teamB
            rooms[room_id]["winning_team"] = team_winners  # <-- This ensures next round uses the correct team!
            win_indices = [game['finish_order'].index(p) for p in team_winners]
            win_indices.sort()
            if win_indices == [0,1]:
                level_up = 4
                win_type = "1-2"
            elif win_indices == [0,2]:
                level_up = 2
                win_type = "1-3"
            else:
                level_up = 1
                win_type = "1-4"
            levels = rooms[room_id]["levels"]
            for p in team_winners:
                levels[p] = get_next_level(levels[p], level_up)
            emit('game_over', {
                'finish_order': game['finish_order'],
                'hands': rooms[room_id]['hands'],
                'levels': rooms[room_id]["levels"],
                'teams': teams,
                'winning_team': team_winners,
                'win_type': win_type,
                'level_up': level_up,
                'trumpSuit': game.get("trumpSuit"),
                'levelRank': game.get("levelRank"),
                'wildCards': game.get("wildCards"),
                'slots': rooms[room_id]["slots"],
                'startingLevels': game.get("startingLevels")
            }, room=room_id)
            del rooms[room_id]['game']
            broadcast_room_update(room_id)
            return
        else:
            start_new_trick(room_id, username)
            return

    game['passes'] = set()
    game['current_winner'] = username

    game['current_play'] = {'player': username, 'cards': cards}
    play_type_label = this_type[0] if this_type else None
    game['turn_index'] = (game['turn_index'] + 1) % len(game['players'])

    emit('game_update', {
        'current_play': game['current_play'],
        'last_play_type': play_type_label,
        'hands': rooms[room_id]['hands'],
        'current_player': game['players'][game['turn_index']],
        'can_end_round': False,
        'passed_players': list(game.get('passes', set())),
        'levels': rooms[room_id]["levels"],
        'teams': rooms[room_id]["teams"],
        'slots': rooms[room_id]["slots"],
        'trumpSuit': game.get("trumpSuit"),
        'levelRank': game.get("levelRank"),
        'wildCards': game.get("wildCards"),
        'startingLevels': game.get("startingLevels")
    }, room=room_id)

@socketio.on('pass_turn')
def handle_pass_turn(data):
    room_id = data.get('roomId')
    username = data.get('username')

    game = rooms[room_id].get('game')
    if not game:
        emit('error_msg', "Game not active.", room=request.sid)
        return

    current_player = game['players'][game['turn_index']]
    if username != current_player:
        emit('error_msg', "Not your turn!", room=request.sid)
        return

    game.setdefault('passes', set()).add(username)
    if 'current_winner' in game:
        non_passed = set(game['players']) - game['passes']
        if len(non_passed) == 1 and game['current_winner'] in non_passed:
            emit('game_update', {
                'current_play': game['current_play'],
                'last_play_type': hand_type(game['current_play']['cards'], level_rank=game.get('levelRank'), trump_suit=game.get('trumpSuit'), wild_cards_enabled=game.get('wildCards'))[0] if game['current_play'] else None,
                'hands': rooms[room_id]['hands'],
                'current_player': game['current_winner'],
                'can_end_round': True,
                'passed_players': list(game.get('passes', set())),
                'levels': rooms[room_id]["levels"],
                'teams': rooms[room_id]["teams"],
                'slots': rooms[room_id]["slots"],
                'trumpSuit': game.get("trumpSuit"),
                'levelRank': game.get("levelRank"),
                'wildCards': game.get("wildCards"),
                'startingLevels': game.get("startingLevels")
            }, room=room_id)
            return

    game['turn_index'] = (game['turn_index'] + 1) % len(game['players'])

    emit('game_update', {
        'current_play': game['current_play'],
        'last_play_type': hand_type(game['current_play']['cards'], level_rank=game.get('levelRank'), trump_suit=game.get('trumpSuit'), wild_cards_enabled=game.get('wildCards'))[0] if game['current_play'] else None,
        'hands': rooms[room_id]['hands'],
        'current_player': game['players'][game['turn_index']],
        'can_end_round': False,
        'passed_players': list(game.get('passes', set())),
        'levels': rooms[room_id]["levels"],
        'teams': rooms[room_id]["teams"],
        'slots': rooms[room_id]["slots"],
        'trumpSuit': game.get("trumpSuit"),
        'levelRank': game.get("levelRank"),
        'wildCards': game.get("wildCards"),
        'startingLevels': game.get("startingLevels")
    }, room=room_id)

@socketio.on('end_round')
def handle_end_round(data):
    room_id = data.get('roomId')
    username = data.get('username')

    game = rooms[room_id].get('game')
    if not game or not game.get('can_end_round', True):
        emit('error_msg', "You can't end the round", room=request.sid)
        return
    if username != game.get('current_winner'):
        emit('error_msg', "Only the current winner can end the round", room=request.sid)
        return
    start_new_trick(room_id, username)

@socketio.on('connect')
def handle_connect():
    print('A client connected, sid:', request.sid)
    emit('message', {'msg': 'Connected to Guandan server!'})

import threading

@socketio.on('disconnect')
def handle_disconnect():
    print('A client disconnected, sid:', request.sid)
    rooms_to_cleanup = []

    # Remove this SID from all rooms (a user might be in multiple rooms in rare cases)
    for room_id, room in list(rooms.items()):
        sids = room.get("connected_sids", set())
        if request.sid in sids:
            sids.remove(request.sid)
            room["connected_sids"] = sids
            # If room is now empty, mark for delayed cleanup
            if not sids:
                rooms_to_cleanup.append(room_id)

    # Delay cleanup by 10 seconds (so if someone rejoins, room is not deleted)
    def delayed_cleanup(room_id):
        import time
        time.sleep(10)
        # Double check room still exists and is still empty
        if room_id in rooms and not rooms[room_id].get("connected_sids"):
            print(f"[Room Cleanup] Deleting room {room_id} after 10s of inactivity.")
            del rooms[room_id]

    for room_id in rooms_to_cleanup:
        threading.Thread(target=delayed_cleanup, args=(room_id,)).start()


if __name__ == "__main__":
    print("Starting Guandan backend with async_mode =", socketio.async_mode)
    socketio.run(app, host="127.0.0.1", port=5000)
