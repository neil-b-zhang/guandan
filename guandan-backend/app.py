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

    players = get_room_players(room_id)

    deck = create_deck()
    shuffle_deck(deck)
    hands = deal_cards(deck, len(players))

    for player, hand in zip(players, hands):
        set_player_hand(room_id, player, hand)

    # Initialize game state with turn tracking
    rooms[room_id]['game'] = {
        'players': players,
        'turn_index': 0,
        'current_play': None,
        'round_active': True
    }

    # Send game started event with current player info
    emit('game_started', {"roomId": room_id, "current_player": players[0]}, room=room_id)
    broadcast_room_update(room_id)

    # Send each player their hand privately
    for player in players:
        hand = get_player_hand(room_id, player)
        emit('deal_hand', {"hand": hand, "username": player}, room=room_id)


@socketio.on('play_cards')
def handle_play_cards(data):
    room_id = data.get('roomId')
    username = data.get('username')
    cards = data.get('cards', [])

    game = rooms[room_id].get('game')
    if not game or not game['round_active']:
        emit('error_msg', "Game not active.", room=request.sid)
        return

    current_player = game['players'][game['turn_index']]
    if username != current_player:
        emit('error_msg', "Not your turn!", room=request.sid)
        return

    player_hand = rooms[room_id]['hands'][username]

    # Basic validation: check player owns all cards played
    if not all(card in player_hand for card in cards):
        emit('error_msg', "You do not have all those cards.", room=request.sid)
        return

    # TODO: Implement Guan Dan-specific move validation here

    # Remove played cards from player's hand
    for card in cards:
        player_hand.remove(card)

    # Update current play on table
    game['current_play'] = {'player': username, 'cards': cards}

    # Advance turn
    game['turn_index'] = (game['turn_index'] + 1) % len(game['players'])

    # Broadcast game update
    emit('game_update', {
        'current_play': game['current_play'],
        'hands': rooms[room_id]['hands'],
        'current_player': game['players'][game['turn_index']]
    }, room=room_id)


@socketio.on('pass_turn')
def handle_pass_turn(data):
    room_id = data.get('roomId')
    username = data.get('username')

    game = rooms[room_id].get('game')
    if not game or not game['round_active']:
        emit('error_msg', "Game not active.", room=request.sid)
        return

    current_player = game['players'][game['turn_index']]
    if username != current_player:
        emit('error_msg', "Not your turn!", room=request.sid)
        return

    # Update current play to pass (empty cards)
    game['current_play'] = {'player': username, 'cards': []}

    # Advance turn
    game['turn_index'] = (game['turn_index'] + 1) % len(game['players'])

    emit('game_update', {
        'current_play': game['current_play'],
        'hands': rooms[room_id]['hands'],
        'current_player': game['players'][game['turn_index']]
    }, room=room_id)


if __name__ == "__main__":
    print("Starting Guandan backend with async_mode =", socketio.async_mode)
    socketio.run(app, host="127.0.0.1", port=5000)
