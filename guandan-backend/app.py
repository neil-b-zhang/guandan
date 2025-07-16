from flask import Flask, jsonify, request
from flask_socketio import SocketIO, emit, join_room as sio_join_room
import threading
import time

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
from game.deck import create_deck, shuffle_deck
from game.hands import hand_type, beats, find_wilds

import logging
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

LEVEL_SEQUENCE = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
SUIT_OPTIONS = ['hearts', 'spades', 'diamonds', 'clubs']

# --- (all your helper functions and class code goes here, unmodified) ---

def level_index(lv):
    try:
        return LEVEL_SEQUENCE.index(lv)
    except Exception:
        return 0

def get_next_level(current, up):
    idx = min(level_index(current) + up, len(LEVEL_SEQUENCE) - 1)
    return LEVEL_SEQUENCE[idx]

def player_is_finished(room_id, player):
    return len(rooms[room_id]['hands'][player]) == 0

def get_finished_players(room_id):
    return [p for p in rooms[room_id]['game']['players'] if player_is_finished(room_id, p)]

def next_player_with_cards(game, room_id, start_idx):
    players = game['players']
    num_players = len(players)
    for offset in range(1, num_players+1):
        idx = (start_idx + offset) % num_players
        player = players[idx]
        if len(rooms[room_id]['hands'][player]) > 0:
            return idx
    return None

def get_last_play_type(game):
    last_play = game.get('current_play')
    if last_play and last_play.get('cards'):
        hand_info = hand_type(
            last_play['cards'],
            game['levelRank'],
            game['trumpSuit'],
            game['wildCards']
        )
        if hand_info:
            return hand_info[0]
    return None
    
def handle_end_of_round(room):
    levels = room['levels']
    teams = room['teams']  # [teamA, teamB]
    finish_order = room['game']['finish_order']
    ace_attempts = room.setdefault('ace_attempts', {0: 0, 1: 0})
    teamA, teamB = teams

    first = finish_order[0] if len(finish_order) > 0 else None
    second = finish_order[1] if len(finish_order) > 1 else None

    print(f"[ROUND END] Finish order: {finish_order}")

    if not first or not second:
        print("[ERROR] Not enough players finished to evaluate end-of-round rules.")
        return {
            "game_over": False,
            "error": "Not enough players finished to determine round outcome.",
            "levels": dict(levels)
        }

    first_team = teamA if first in teamA else teamB
    second_team = teamA if second in teamA else teamB
    same_team_win = first_team == second_team
    winners_team = first_team if same_team_win else first_team
    losers_team = teamB if winners_team == teamA else teamA

    win_indices = [finish_order.index(p) for p in winners_team if p in finish_order]
    win_indices.sort()
    win_type = None
    level_up = 1

    if win_indices == [0, 1]:
        win_type = "1-2"
        level_up = 4
    elif win_indices == [0, 2]:
        win_type = "1-3"
        level_up = 2
    else:
        win_type = "1-4"
        level_up = 1

    ace_level = LEVEL_SEQUENCE[-1]
    declarer_team = winners_team
    declarer_at_ace = all(levels.get(p) == ace_level for p in declarer_team)
    game_just_won = False
    ace_reset = False
    ace_loser_ace_bomb = False

    if declarer_at_ace:
        team_id = 0 if declarer_team == teamA else 1
        if win_type in ("1-2", "1-3"):
            game_just_won = True
            ace_attempts[team_id] = 0
        elif win_type == "1-4":
            ace_attempts[team_id] += 1
            if ace_attempts[team_id] >= 3:
                for p in declarer_team:
                    levels[p] = LEVEL_SEQUENCE[0]
                ace_reset = True
                ace_attempts[team_id] = 0
        elif losers_team == declarer_team:
            ace_attempts[team_id] += 1
            last_play = room['game'].get('last_play_cards', [])
            if last_play and all(card[0] == 'A' for card in last_play):
                for p in declarer_team:
                    levels[p] = LEVEL_SEQUENCE[0]
                ace_loser_ace_bomb = True
                ace_attempts[team_id] = 0

    if not (declarer_at_ace and (game_just_won or ace_reset or ace_loser_ace_bomb)):
        for p in declarer_team:
            levels[p] = get_next_level(levels[p], level_up)
            if levels[p] not in LEVEL_SEQUENCE:
                levels[p] = ace_level

    if first in losers_team:
        for p in losers_team:
            levels[p] = get_next_level(levels[p], level_up)
            if levels[p] not in LEVEL_SEQUENCE:
                levels[p] = ace_level
        declarer_team = losers_team
        if all(levels[p] == ace_level for p in declarer_team):
            team_id = 0 if declarer_team == teamA else 1
            ace_attempts[team_id] = 0

    room['levels'] = levels
    room['ace_attempts'] = ace_attempts
    room['winning_team'] = declarer_team
    room['win_type'] = win_type
    room['level_up'] = level_up

    print(f"[ROUND RESULT] Win type: {win_type}, Declarer team: {declarer_team}, Levels: {levels}")

    return {
        "game_over": game_just_won,
        "winning_team": declarer_team,
        "win_type": win_type,
        "levels": dict(levels),
        "ace_attempts": dict(ace_attempts)
    }

def determine_tributes(room):
    finish_order = room.get('game', {}).get('finish_order', [])
    teams = room.get('teams', [[], []])
    if len(finish_order) < 2:
        return None

    first = finish_order[0]
    second = finish_order[1] if len(finish_order) > 1 else None
    last = finish_order[-1]
    second_last = finish_order[-2] if len(finish_order) > 2 else None

    teamA = set(teams[0])
    teamB = set(teams[1])

    tribute_info = []
    blockable = False

    if first in teamA and second in teamA:
        tribute_info.append({'from': last, 'to': first})
        tribute_info.append({'from': second_last, 'to': second})
        blockable = True
    elif first in teamA and last in teamB:
        tribute_info.append({'from': last, 'to': first})
        blockable = True
    elif first in teamA and last in teamA:
        tribute_info.append({'from': last, 'to': first})
        blockable = True

    return {
        'tributes': tribute_info,
        'blockable': blockable,
        'step': 'pay',
        'tribute_cards': {},
        'exchange_cards': {}
    }

def deal_to_all_players(room_id):
    """
    Patch: replaces per-user hand deals.
    Broadcast all hands to all players in room after dealing/tribute/return.
    """
    room = rooms[room_id]
    socketio.emit("all_hands", {
        "hands": {p: room['hands'][p] for p in room['players']}
    }, room=room_id)

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

def emit_game_update(room_id, current_player, play_type=None, can_end_round=False):
    game = rooms[room_id]['game']
    emit('game_update', {
        'current_play': game['current_play'],
        'last_play_type': play_type,
        'hands': rooms[room_id]['hands'],
        'current_player': current_player,
        'can_end_round': can_end_round,
        'passed_players': list(game.get('passes', [])),
        'levels': rooms[room_id]["levels"],
        'teams': rooms[room_id]["teams"],
        'slots': rooms[room_id]["slots"],
        'trumpSuit': game.get("trumpSuit"),
        'levelRank': game.get("levelRank"),
        'wildCards': game.get("wildCards"),
        'startingLevels': game.get("startingLevels"),
        'finished_players': get_finished_players(room_id),
        'finish_order': game.get('finish_order', [])
    }, room=room_id)

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

@app.route("/")
def index():
    return jsonify({"status": "Guandan backend running"})

@socketio.on('create_room')
def handle_create_room(data):
    username = data.get('username')
    room_name = data.get('roomName', '')
    card_back = data.get('cardBack', 'red')
    wild_cards = data.get('wildCards', True)
    trump_suit = data.get('trumpSuit', 'hearts')
    starting_levels = data.get('startingLevels', ["2", "2", "2", "2"])

    if not username:
        emit('error_msg', "Username required.", room=request.sid)
        return

    if room_name:
        room_id = room_name.strip().lower().replace(" ", "-")
    else:
        room_id = generate_room_id()

    if room_id in rooms:
        emit('error_msg', "Game lobby already exists with that name", room=request.sid)
        return

    for existing in rooms.values():
        if username in existing.get("players", []):
            emit('error_msg', f"Username '{username}' already exists in another room.", room=request.sid)
            return

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
        "connected_sids": [request.sid]
    }
    print(f"[rooms.py] Room {room_id} created with settings {rooms[room_id]['settings']}")

    sio_join_room(room_id)
    rooms[room_id].setdefault("connected_sids", []).append(request.sid)

    emit('room_joined', {
        "roomId": room_id,
        "username": username,
        "players": [username],
        "slots": rooms[room_id]["slots"],
        "settings": rooms[room_id]["settings"]
    }, room=request.sid)

@socketio.on('register_sid')
def handle_register_sid(data):
    room_id = data.get('roomId')
    username = data.get('username')
    sid = request.sid
    if room_id in rooms and username:
        rooms[room_id].setdefault('sids', {})[username] = sid
        sio_join_room(room_id, sid=sid)  # Critical: ensure this socket is in the room for broadcasts!
        print(f"[SID] Registered sid for {username} in room {room_id}: {sid}")
        room = rooms[room_id]
        players = room.get("players", [])
        sids = room.get("sids", {})
        print(f"[DEBUG] register_sid check: players={players}, sids={list(sids.keys())}, dealt_players={room.get('dealt_players')}")
        if (
            "game" in room
            and len(players) == 4
            and all(player in sids for player in players)
            and not room.get("dealt_players")
        ):
            print("[SID] All SIDs registered. Scheduling deal_to_all_players...")
            threading.Timer(0.3, deal_to_all_players, args=(room_id,)).start()

def broadcast_room_update(room_id):
    if room_id not in rooms:
        return
    room = rooms[room_id]
    emit('room_update', {
        "roomId": room_id,
        "players": room.get("players", []),
        "slots": room.get("slots", [None, None, None, None]),
        "readyStates": room.get("ready", {}),
        "settings": room.get("settings", {}),
        "teams": room.get("teams", [[], []]),
        "levels": room.get("levels", {}),
        "startingLevels": room["settings"].get("startingLevels", ["2","2","2","2"])
    }, room=room_id)


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
    start_new_game_round(room_id)

@socketio.on('deal_hand')
def handle_deal_hand(data):
    room_id = data['roomId']
    username = data['username']
    room = rooms.get(room_id)
    if not room:
        return

    player_hand = room.get('hands', {}).get(username)
    if player_hand:
        socketio.emit('deal_hand', {
            'username': username,
            'hand': room['hands'][username]
        }, room=room_id)

    if 'dealt_players' not in room:
        room['dealt_players'] = []
    if username not in room['dealt_players']:
        room['dealt_players'].append(username)

def initiate_tribute_phase(room_id):
    room = rooms[room_id]
    last_finish_order = room.get("last_finish_order") or room.get("game", {}).get("finish_order", [])
    if not last_finish_order or len(last_finish_order) < 2:
        print("[TRIBUTE] No valid finish order; skipping tribute phase.")
        return

    teams = room["teams"]
    teamA = set(teams[0])
    teamB = set(teams[1])

    tribute_state = {
        "step": "pay",
        "payers": [],
        "recipients": [],
        "tributes": {},
        "return_cards": {},
        "blockable": False,
        "blocked": False,
        "type": "",
        "info": "",
    }

    if (last_finish_order[0] in teamA and last_finish_order[1] in teamA) or \
       (last_finish_order[0] in teamB and last_finish_order[1] in teamB):
        # 1-2 win: both losers pay tribute
        losers = [last_finish_order[-1], last_finish_order[-2]]
        winners = [last_finish_order[0], last_finish_order[1]]
        tribute_state["payers"] = losers
        tribute_state["recipients"] = winners
        tribute_state["blockable"] = True
        tribute_state["type"] = "1-2"
        tribute_state["info"] = "Both losers must pay tribute to 1st and 2nd place players."
    else:
        # 1-3 or 1-4 win: only last pays tribute to 1st
        tribute_state["payers"] = [last_finish_order[-1]]
        tribute_state["recipients"] = [last_finish_order[0]]
        tribute_state["blockable"] = True
        if len(set(last_finish_order[:3])) == 3:
            tribute_state["type"] = "1-3"
            tribute_state["info"] = "Last place must pay tribute to 1st place player."
        else:
            tribute_state["type"] = "1-4"
            tribute_state["info"] = "Last place must pay tribute to 1st place player."

    room["tribute_state"] = tribute_state

    print(f"[TRIBUTE] Tribute phase started. State: {tribute_state}")
    socketio.emit("tribute_start", tribute_state, room=room_id)


def start_new_game_round(room_id):
    room = rooms[room_id]
    slots = room["slots"]
    players = [u for u in slots if u]
    room["players"] = players
    deck = create_deck()
    shuffle_deck(deck)

    hands = []
    for _ in range(len(players)):
        hand = [deck.pop() for _ in range(1)]
        hands.append(hand)
    for player, hand in zip(players, hands):
        set_player_hand(room_id, player, hand)

    starting_levels = room["settings"].get("startingLevels", ["2", "2", "2", "2"])
    levels = room.get("levels", {})
    if not levels or any(lv not in LEVEL_SEQUENCE for lv in levels.values()):
        levels = {}
        for i, player in enumerate(slots):
            if player:
                levels[player] = starting_levels[i]
    room["levels"] = levels

    teams = get_teams_from_slots(slots)
    room["teams"] = teams

    winning_team = room.get("winning_team", teams[0])
    team_lvls = [levels[p] for p in winning_team]
    current_level = min(team_lvls, key=lambda lv: LEVEL_SEQUENCE.index(lv))
    trump_suit = room["settings"].get("trumpSuit", "hearts")
    wild_cards = room["settings"].get("wildCards", True)

    game = {
        'players': players,
        'turn_index': 0,
        'current_play': None,
        'round_active': True,
        'passes': [],
        'current_winner': None,
        'finish_order': room.get("finish_order", []),
        'trumpSuit': trump_suit,
        'levelRank': current_level,
        'wildCards': wild_cards,
        'startingLevels': starting_levels,
        'round_number': room.get("game", {}).get("round_number", 0) + 1
    }
    room['game'] = game
    room['ace_attempts'] = {0: 0, 1: 0}
    room.pop('tribute_state', None)

    emit('game_started', {
        "roomId": room_id,
        "current_player": players[0],
        "levels": levels,
        "teams": teams,
        "slots": slots,
        "settings": room["settings"],
        "trumpSuit": trump_suit,
        "levelRank": current_level,
        "wildCards": wild_cards,
        "startingLevels": starting_levels,
        "hands": {p: room['hands'][p] for p in players}
    }, room=room_id)

    broadcast_room_update(room_id)
    deal_to_all_players(room_id)  

    # Only trigger tribute phase after the first round
    round_num = room['game']['round_number']
    if round_num > 1:
        initiate_tribute_phase(room_id)


def start_new_trick(room_id, winner_username):
    game = rooms[room_id]['game']
    players = game['players']
    idx = players.index(winner_username)
    num_players = len(players)
    next_player = None
    for i in range(num_players):
        candidate_idx = (idx + i) % num_players
        candidate = players[candidate_idx]
        if len(rooms[room_id]['hands'][candidate]) > 0:
            next_player = candidate
            break
    game['turn_index'] = players.index(next_player) if next_player else 0
    game['current_play'] = None
    game['passes'] = []
    game['current_winner'] = next_player

    print(f"[EMIT game_update] Called from start_new_trick, next_player: {next_player}")
    emit('game_update', {
        'current_play': None,
        'last_play_type': None,
        'hands': rooms[room_id]['hands'],
        'current_player': next_player,
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

    if username != game['players'][game['turn_index']]:
        emit('error_msg', "Not your turn!", room=request.sid)
        return

    # Copy the player's hand for reference
    player_hand = rooms[room_id]['hands'][username]

    # --- VALIDATE HAND TYPE FIRST ---
    this_type = hand_type(cards, game['levelRank'], game['trumpSuit'], game['wildCards'])
    if not this_type:
        emit('error_msg', "Invalid hand type!", room=request.sid)
        return

    if game['current_play'] and game['current_play']['cards']:
        if not beats(game['current_play'], {'player': username, 'cards': cards},
                     game['levelRank'], game['trumpSuit'], game['wildCards']):
            emit('error_msg', "Your play must beat the previous hand.", room=request.sid)
            return

    # --- Build a list of indexes to remove ---
    hand_indexes_to_remove = []
    hand_copy = list(player_hand)  # Copy for matching
    for play_card in cards:
        if play_card in hand_copy:
            idx = hand_copy.index(play_card)
            hand_indexes_to_remove.append(idx)
            hand_copy[idx] = None  # Mark as used
        else:
            # Try to use a wild if possible
            wilds = find_wilds(hand_copy, game['levelRank'], game['trumpSuit'], game['wildCards'])
            if wilds:
                wild_idx = hand_copy.index(wilds[0])
                hand_indexes_to_remove.append(wild_idx)
                hand_copy[wild_idx] = None
            else:
                emit('error_msg', "You do not have the cards you're trying to play.", room=request.sid)
                return

    # --- Remove the selected cards from the original hand, preserving order ---
    for idx in sorted(hand_indexes_to_remove, reverse=True):
        del player_hand[idx]

    print(f"[PLAY_CARDS] {username} played: {cards} | Type: {this_type[0]}")

    rooms[room_id]['hands'][username] = player_hand
    deal_to_all_players(room_id)

    game['current_play'] = {'player': username, 'cards': cards}
    game['passes'] = []
    game['current_winner'] = username
    play_type_label = this_type[0]

    if len(player_hand) == 0 and username not in game['finish_order']:
        game['finish_order'].append(username)
        print(f"[FINISH] {username} has finished. Transferring current_winner to their partner.")
        teams = rooms[room_id]["teams"]
        for team in teams:
            if username in team:
                partner = next(p for p in team if p != username)
                break
        print(f"[FINISH] New current_winner is {partner}")
        game['current_winner'] = partner

    teams = rooms[room_id]['teams']
    finished = get_finished_players(room_id)
    team_a_done = all(p in finished for p in teams[0])
    team_b_done = all(p in finished for p in teams[1])

    if team_a_done or team_b_done:
        print(f"[END OF HAND] {username} ended the hand.")
        emit_game_update(room_id, current_player=None, play_type=play_type_label)
        handle_end_of_hand(room_id, play_type_label)
        return

    next_idx = next_player_with_cards(game, room_id, game['turn_index'])
    if next_idx is not None:
        game['turn_index'] = next_idx
        print(f"[NEXT TURN] current_player: {game['players'][next_idx]}, current_winner: {game.get('current_winner')}")
        emit_game_update(room_id, current_player=game['players'][next_idx], play_type=play_type_label)
    else:
        print("[NEXT TURN] No next player found, emitting null update")
        emit_game_update(room_id, current_player=None, play_type=play_type_label)



@socketio.on('pass_turn')
def handle_pass_turn(data):
    room_id = data.get('roomId')
    username = data.get('username')

    game = rooms[room_id].get('game')
    if not game or username != game['players'][game['turn_index']]:
        emit('error_msg', "Invalid pass action", room=request.sid)
        return

    # Add the player to the passes list (no sets!)
    if username not in game.setdefault('passes', []):
        game['passes'].append(username)

    winner = game.get('current_winner')

    print("\n--- PASS TURN DEBUG ---")
    print(f"Room: {room_id}")
    print(f"Username passing: {username}")
    print(f"Current winner: {winner}")
    print(f"Game passes: {game.get('passes')}")
    print(f"Players in game: {game['players']}")
    print(f"Finished players: {get_finished_players(room_id)}")

    players_in = set(p for p in game['players'] if not player_is_finished(room_id, p))
    non_passed = players_in - set(game['passes'])
    print(f"Players with cards still in trick: {players_in}")
    print(f"Non-passed players: {non_passed}")

    if len(non_passed) == 0:
        if player_is_finished(room_id, winner):
            teams = rooms[room_id]["teams"]
            for team in teams:
                if winner in team:
                    partner = next(p for p in team if p != winner)
                    break
            print(f"[ALL PASSED] Winner {winner} is finished. Partner {partner} should be prompted to end round.")
            emit_game_update(
                room_id,
                current_player=partner,
                play_type=get_last_play_type(game),
                can_end_round=True
            )
        else:
            print(f"[ALL PASSED] Winner {winner} will continue and can end round.")
            emit_game_update(
                room_id,
                current_player=winner,
                play_type=get_last_play_type(game),
                can_end_round=True
            )
        return

    if len(non_passed) == 1 and winner in non_passed:
        print(f"[CHECK] Only one player not passed: {winner}")
        print(f"[CHECK] Is winner finished? {player_is_finished(room_id, winner)}")

        if player_is_finished(room_id, winner):
            teams = rooms[room_id]["teams"]
            for team in teams:
                if winner in team:
                    partner = next(p for p in team if p != winner)
                    break
            print(f"[TRICK ENDS] {winner} is out of cards. Partner {partner} may end round.")
            emit_game_update(
                room_id,
                current_player=partner,
                play_type=get_last_play_type(game),
                can_end_round=True
            )
        else:
            print(f"[TRICK ENDS] {winner} leads next.")
            emit_game_update(
                room_id,
                current_player=winner,
                play_type=get_last_play_type(game),
                can_end_round=True
            )
        return

    next_idx = next_player_with_cards(game, room_id, game['turn_index'])
    if next_idx is not None:
        game['turn_index'] = next_idx
        print(f"[NEXT TURN] Passing to: {game['players'][next_idx]}")
        emit_game_update(
            room_id,
            current_player=game['players'][next_idx],
            play_type=get_last_play_type(game)
        )
    else:
        print("[FALLBACK] No next player found.")
        emit_game_update(room_id, current_player=None)

@socketio.on('end_round')
def handle_end_round(data):
    room_id = data.get('roomId')
    username = data.get('username')

    game = rooms[room_id].get('game')
    if not game or not game.get('can_end_round', True):
        emit('error_msg', "You can't end the round", room=request.sid)
        return

    winner = game.get('current_winner')

    if username == winner:
        start_new_trick(room_id, username)
        return

    if player_is_finished(room_id, winner):
        teams = rooms[room_id]["teams"]
        for team in teams:
            if winner in team and username in team and username != winner:
                start_new_trick(room_id, username)
                return

    emit('error_msg', "Only the current winner or their partner (if finished) can end the round", room=request.sid)

@socketio.on('pay_tribute')
def handle_pay_tribute(data):
    room_id = data['roomId']
    from_player = data['from']
    card = data['card']
    room = rooms.get(room_id)
    if not room:
        return

    tribute_state = room.get('tribute_state')
    if not tribute_state:
        return

    tribute_state['tribute_cards'][from_player] = card

    if len(tribute_state['tribute_cards']) == len(tribute_state['tributes']):
        tribute_state['step'] = 'return'
        socketio.emit('tribute_prompt_return', {'tribute_state': tribute_state}, room=room_id)
    else:
        socketio.emit('tribute_update', {'tribute_state': tribute_state}, room=room_id)

@socketio.on('return_tribute')
def handle_return_tribute(data):
    room_id = data['roomId']
    from_player = data['from']
    to_player = data['to']
    card = data['card']
    room = rooms.get(room_id)
    if not room:
        return

    tribute_state = room.get('tribute_state')
    if not tribute_state:
        return

    tribute_state['exchange_cards'][from_player] = {'to': to_player, 'card': card}

    if len(tribute_state['exchange_cards']) == len(tribute_state['tributes']):
        tribute_state['step'] = 'done'
        hands = room['hands']

        for t in tribute_state['tributes']:
            from_player = t['from']
            to_player = t['to']
            tribute_card = tribute_state['tribute_cards'][from_player]
            return_card = tribute_state['exchange_cards'][to_player]['card']

            if tribute_card == return_card:
                continue

            try:
                hands[from_player].remove(tribute_card)
                hands[to_player].remove(return_card)
                hands[from_player].append(return_card)
                hands[to_player].append(tribute_card)
            except Exception as e:
                print("[TRIBUTE] Card transfer error:", e)

        socketio.emit('tribute_complete', {'tribute_state': tribute_state, 'hands': hands}, room=room_id)
        room['tribute_state'] = None
    else:
        socketio.emit('tribute_update', {'tribute_state': tribute_state}, room=room_id)

@socketio.on('connect')
def handle_connect():
    print('A client connected, sid:', request.sid)
    emit('message', {'msg': 'Connected to Guandan server!'})

import threading

@socketio.on('disconnect')
def handle_disconnect():
    print('A client disconnected, sid:', request.sid)
    rooms_to_cleanup = []

    for room_id, room in list(rooms.items()):
        sids = room.get("connected_sids", [])
        if request.sid in sids:
            sids.remove(request.sid)
            room["connected_sids"] = sids
            if not sids:
                rooms_to_cleanup.append(room_id)

    def delayed_cleanup(room_id):
        import time
        time.sleep(10)
        if room_id in rooms and not rooms[room_id].get("connected_sids"):
            print(f"[Room Cleanup] Deleting room {room_id} after 10s of inactivity.")
            del rooms[room_id]

    for room_id in rooms_to_cleanup:
        threading.Thread(target=delayed_cleanup, args=(room_id,)).start()

def handle_end_of_hand(room_id, play_type_label):
    game = rooms[room_id]['game']
    room = rooms[room_id]

    finish_order = game.get("finish_order", [])
    print(f"[ROUND END] Finish order: {finish_order}")

    result = handle_end_of_round(room)
    print(f"[ROUND RESULT] Win type: {room.get('win_type')}, Declarer team: {room.get('winning_team')}, Levels: {room['levels']}")

    result["slots"] = rooms[room_id].get("slots", [None, None, None, None])
    print("[ROUND SUMMARY] Sending to frontend:", result)

    team_levels = [int(room["levels"].get(p, 2)) for p in room["teams"][0]]
    level_rank = min(team_levels)

    game["round_number"] = game.get("round_number", 1) + 1

    result["round_number"] = game["round_number"]
    result["level_rank"] = str(level_rank)

    emit("round_summary", {
        "roomId": room_id,
        "finishOrder": finish_order,
        "result": result
    }, room=room_id)

    del rooms[room_id]["game"]

if __name__ == "__main__":
    print("Starting Guandan backend with async_mode =", socketio.async_mode)
    socketio.run(app, host="127.0.0.1", port=5000)
