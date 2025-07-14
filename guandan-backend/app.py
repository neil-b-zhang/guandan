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
    rooms
)
from game.deck import create_deck, shuffle_deck, deal_cards
from game.hands import hand_type, beats  # NEW

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

@app.route("/")
def index():
    return jsonify({"status": "Guandan backend running"})

@socketio.on('connect')
def handle_connect():
    print('A client connected, sid:', request.sid)
    emit('message', {'msg': 'Connected to Guandan server!'})

@socketio.on('disconnect')
def handle_disconnect():
    print('A client disconnected, sid:', request.sid)

def broadcast_room_update(room_id):
    if room_id in rooms:
        players = get_room_players(room_id)
        ready_states = get_ready_states(room_id)
        emit('room_update', {
            "roomId": room_id,
            "players": players,
            "readyStates": ready_states
        }, room=room_id)
        print(f"Broadcasted room_update to room {room_id}: players={players}, ready={ready_states}")

def start_new_game_round(room_id):
    players = get_room_players(room_id)
    deck = create_deck()
    shuffle_deck(deck)
    hands = deal_cards(deck, len(players))
    for player, hand in zip(players, hands):
        set_player_hand(room_id, player, hand)
    rooms[room_id]['game'] = {
        'players': players,
        'turn_index': 0,
        'current_play': None,
        'round_active': True,
        'passes': set(),
        'current_winner': None,
        'finish_order': []
    }
    emit('game_started', {"roomId": room_id, "current_player": players[0]}, room=room_id)
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
        'passed_players': []
    }, room=room_id)

@socketio.on('create_room')
def handle_create_room(data):
    print("Received create_room event with data:", data)
    username = data.get('username')
    card_back = data.get('cardBack')
    wild_cards = data.get('wildCards')
    if not username:
        emit('error_msg', "Username required", room=request.sid)
        return

    room_id = create_room(username, card_back, wild_cards)
    sio_join_room(room_id)
    print(f"Room {room_id} created by {username}")

    emit('room_joined', {
        "roomId": room_id,
        "username": username,
        "players": [username],
        "settings": {
            "cardBack": card_back,
            "wildCards": wild_cards
        }
    }, room=request.sid)
    broadcast_room_update(room_id)

@socketio.on('join_room')
def handle_join_room(data):
    print("Received join_room event with data:", data)
    username = data.get('username')
    room_id = data.get('roomId', '').lower()
    if not username or not room_id:
        emit('error_msg', "Username and Room ID required", room=request.sid)
        return

    if join_existing_room(username, room_id):
        sio_join_room(room_id)
        print(f"{username} joined room {room_id}")
        emit('room_joined', {
            "roomId": room_id,
            "username": username,
            "players": get_room_players(room_id),
            "settings": rooms[room_id]["settings"]
        }, room=request.sid)
        broadcast_room_update(room_id)
    else:
        emit('error_msg', "Room does not exist", room=request.sid)

@socketio.on('set_ready')
def handle_set_ready(data):
    room_id = data.get('roomId')
    username = data.get('username')
    ready = data.get('ready', False)
    set_player_ready(room_id, username, ready)
    print(f"{username} set ready={ready} in room {room_id}")
    broadcast_room_update(room_id)

@socketio.on('start_game')
def handle_start_game(data):
    room_id = data.get('roomId')
    username = data.get('username')
    if not all_players_ready(room_id):
        emit('error_msg', "Not all players are ready!", room=request.sid)
        return
    print(f"Game started in room {room_id} by {username}")
    start_new_game_round(room_id)

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

    # --- HAND VALIDATION (NEW) ---
    this_type = hand_type(cards)
    if not this_type:
        emit('error_msg', "Invalid hand type! Allowed: Single, Pair, Triple, Full House, Straight (5), Tube (3 consecutive pairs), Plate (2 consecutive triples), Bomb, Joker Bomb.", room=request.sid)
        return

    last_play = game['current_play']
    # Must beat previous play if there was one
    if last_play and last_play['cards']:
        # Use beats() from hands.py
        if not beats(last_play, {'player': username, 'cards': cards}):
            emit('error_msg', "Your play must beat the previous hand (matching type/length and higher rank, or a Bomb/Joker Bomb).", room=request.sid)
            return

    # Remove played cards from hand
    for card in cards:
        player_hand.remove(card)

    # Check for trick/game end (player finishes hand)
    if len(player_hand) == 0:
        game['finish_order'].append(username)
        remaining_players = [p for p in game['players'] if len(rooms[room_id]['hands'][p]) > 0]
        if len(remaining_players) == 1:
            # Game over
            game['finish_order'].append(remaining_players[0])
            emit('game_over', {
                'finish_order': game['finish_order'],
                'hands': rooms[room_id]['hands']
            }, room=room_id)
            print(f"Game over! Finish order: {game['finish_order']}")
            del rooms[room_id]['game']
            return
        else:
            print(f"Trick ended! {username} wins trick and starts next.")
            start_new_trick(room_id, username)
            return

    # Reset passes; this is a new winning play
    game['passes'] = set()
    game['current_winner'] = username

    # Update play and advance turn
    game['current_play'] = {'player': username, 'cards': cards}

    # --- NEW: Add hand type to last play ---
    play_type_label = hand_type(cards)[0] if hand_type(cards) else None

    game['turn_index'] = (game['turn_index'] + 1) % len(game['players'])

    emit('game_update', {
        'current_play': game['current_play'],
        'last_play_type': play_type_label,
        'hands': rooms[room_id]['hands'],
        'current_player': game['players'][game['turn_index']],
        'can_end_round': False,
        'passed_players': list(game.get('passes', set()))
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

    # Add this player to passes set
    game.setdefault('passes', set()).add(username)

    # If all players except one (the last winning player) have passed,
    # allow current_winner to end round
    if 'current_winner' in game:
        non_passed = set(game['players']) - game['passes']
        if len(non_passed) == 1 and game['current_winner'] in non_passed:
            emit('game_update', {
                'current_play': game['current_play'],
                'last_play_type': hand_type(game['current_play']['cards'])[0] if game['current_play'] else None,
                'hands': rooms[room_id]['hands'],
                'current_player': game['current_winner'],
                'can_end_round': True,
                'passed_players': list(game.get('passes', set()))
            }, room=room_id)
            return

    # Advance turn to next player
    game['turn_index'] = (game['turn_index'] + 1) % len(game['players'])

    emit('game_update', {
        'current_play': game['current_play'],
        'last_play_type': hand_type(game['current_play']['cards'])[0] if game['current_play'] else None,
        'hands': rooms[room_id]['hands'],
        'current_player': game['players'][game['turn_index']],
        'can_end_round': False,
        'passed_players': list(game.get('passes', set()))
    }, room=room_id)

@socketio.on('end_round')
def handle_end_round(data):
    room_id = data.get('roomId')
    username = data.get('username')
    game = rooms[room_id].get('game')
    # Only the current_winner can end the round
    if not game or username != game.get('current_winner'):
        emit('error_msg', "You can't end the round.", room=request.sid)
        return
    print(f"Trick ended by winner {username}; starts next.")
    start_new_trick(room_id, username)

if __name__ == "__main__":
    print("Starting Guandan backend with async_mode =", socketio.async_mode)
    socketio.run(app, host="127.0.0.1", port=5000)
