# guandan-backend/app.py

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

    # Send confirmation to creator
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

    emit('game_started', {"roomId": room_id}, room=room_id)

    # Send each player their hand privately
    for player in players:
        hand = get_player_hand(room_id, player)
        sid = None
        for sid_key, socket in socketio.server.manager.rooms['/'].items():
            if player in socket:
                sid = sid_key
                break
        if sid:
            emit('deal_hand', {"hand": hand}, room=sid)
        
if __name__ == "__main__":
    print("Starting Guandan backend with async_mode =", socketio.async_mode)
    socketio.run(app, host="127.0.0.1", port=5000)
