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

def start_new_round(room_id):
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
        'current_winner': None
    }
    emit('game_started', {"roomId": room_id, "current_player": players[0]}, room=room_id)
    broadcast_room_update(room_id)
    for player in players:
        hand = get_player_hand(room_id, player)
        emit('deal_hand', {"hand": hand, "username": player}, room=room_id)

@socketio.on('start_game')
def handle_start_game(data):
    room_id = data.get('roomId')
    username = data.get('username')
    if not all_players_ready(room_id):
        emit('error_msg', "Not all players are ready!", room=request.sid)
        return
    print(f"Game started in room {room_id} by {username}")
    start_new_round(room_id)

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

    # 1. Check player owns all cards played
    if not all(card in player_hand for card in cards):
        emit('error_msg', "You do not have all those cards.", room=request.sid)
        return

    # 2. Must play at least one card
    if len(cards) == 0:
        emit('error_msg', "You must select cards to play or use Pass.", room=request.sid)
        return

    # 3. All cards must be the same rank (ignoring wilds/jokers for now)
    ranks = [card[:-1] if not card.startswith("Jo") else card for card in cards]
    if len(set(ranks)) != 1:
        emit('error_msg', "All cards played must be the same rank.", room=request.sid)
        return

    # --- Bomb/Joker Bomb Helper Functions ---
    def is_bomb(cards):
        jokers = set(['JoB', 'JoR'])
        if len(cards) == 2 and set(cards) <= jokers:
            return 'joker_bomb'
        ranks_for_bomb = [card[:-1] if not card.startswith("Jo") else card for card in cards if card not in jokers]
        if len(cards) >= 4 and len(set(ranks_for_bomb)) == 1:
            return 'bomb'
        return None

    # Must beat previous play
    last_play = game['current_play']
    this_bomb = is_bomb(cards)
    rank_order = ['3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A', '2', 'JoB', 'JoR']
    def rank_index(r):
        if r in ['JoB', 'JoR']:
            return rank_order.index(r)
        return rank_order.index(r.upper())

    if last_play and last_play['cards']:
        last_cards = last_play['cards']
        last_bomb = is_bomb(last_cards)
        last_ranks = [c[:-1] if not c.startswith("Jo") else c for c in last_cards]
        last_count = len(last_cards)
        last_rank = last_ranks[0] if last_ranks else None

        if last_bomb:
            if this_bomb == 'joker_bomb' and last_bomb != 'joker_bomb':
                pass
            elif this_bomb == last_bomb and len(cards) == len(last_cards):
                played_rank = ranks[0]
                if rank_index(played_rank) <= rank_index(last_rank):
                    emit('error_msg', "Your bomb is not strong enough to beat the last bomb.", room=request.sid)
                    return
            else:
                emit('error_msg', "You must play a higher bomb to beat the last bomb.", room=request.sid)
                return
        elif this_bomb:
            pass
        else:
            if len(cards) != last_count:
                emit('error_msg', f"You must play {last_count} cards to beat the previous play.", room=request.sid)
                return
            played_rank = ranks[0]
            if rank_index(played_rank) <= rank_index(last_rank):
                emit('error_msg', "Your play must be a higher rank than the last play.", room=request.sid)
                return

    # Remove played cards from hand
    for card in cards:
        player_hand.remove(card)

    # Check for round end (player finishes hand)
    if len(player_hand) == 0:
        game['round_active'] = False
        emit('round_end', {
            'winner': username,
            'hands': rooms[room_id]['hands']
        }, room=room_id)
        print(f"Round ended! {username} wins.")
        return

    # Reset passes; this is a new winning play
    game['passes'] = set()
    game['current_winner'] = username

    # Update play and advance turn
    game['current_play'] = {'player': username, 'cards': cards}
    game['turn_index'] = (game['turn_index'] + 1) % len(game['players'])

    emit('game_update', {
        'current_play': game['current_play'],
        'hands': rooms[room_id]['hands'],
        'current_player': game['players'][game['turn_index']],
        'can_end_round': False
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

    # Add this player to passes set
    game.setdefault('passes', set()).add(username)

    # If all players except one (the last winning player) have passed,
    # allow current_winner to end round
    if 'current_winner' in game:
        non_passed = set(game['players']) - game['passes']
        if len(non_passed) == 1 and game['current_winner'] in non_passed:
            emit('game_update', {
                'current_play': game['current_play'],
                'hands': rooms[room_id]['hands'],
                'current_player': game['current_winner'],
                'can_end_round': True
            }, room=room_id)
            return

    # Advance turn to next player
    game['turn_index'] = (game['turn_index'] + 1) % len(game['players'])

    emit('game_update', {
        'current_play': game['current_play'],
        'hands': rooms[room_id]['hands'],
        'current_player': game['players'][game['turn_index']],
        'can_end_round': False
    }, room=room_id)

@socketio.on('end_round')
def handle_end_round(data):
    room_id = data.get('roomId')
    username = data.get('username')
    game = rooms[room_id].get('game')
    # Only the current_winner can end the round
    if not game or not game['round_active'] or username != game.get('current_winner'):
        emit('error_msg', "You can't end the round.", room=request.sid)
        return
    game['round_active'] = False
    emit('round_end', {
        'winner': username,
        'hands': rooms[room_id]['hands']
    }, room=room_id)
    print(f"Round ended by winner {username}.")

if __name__ == "__main__":
    print("Starting Guandan backend with async_mode =", socketio.async_mode)
    socketio.run(app, host="127.0.0.1", port=5000)
