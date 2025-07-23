from collections import Counter

RANK_ORDER = ['3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A', '2']
SUIT_ORDER = ['clubs', 'diamonds', 'hearts', 'spades']
JOKERS = ['JoB', 'JoR']

def parse_card(card):
    if card in JOKERS:
        return {'rank': card, 'suit': None}
    if len(card) == 2:
        rank, suit = card[0], card[1]
    elif len(card) == 3:
        rank, suit = card[:2], card[2]
    else:
        raise ValueError("Bad card: " + card)
    suit_map = {'C':'clubs','D':'diamonds','H':'hearts','S':'spades'}
    return {'rank': rank, 'suit': suit_map[suit.upper()]}

def card_rank(card):  # Returns rank str
    return parse_card(card)['rank']

def card_suit(card):  # Returns suit str or None
    return parse_card(card)['suit']

def rank_index(rank):
    if rank in JOKERS:
        return 100 + JOKERS.index(rank)
    return RANK_ORDER.index(rank)

def is_consecutive(ranks):
    idxs = [rank_index(r) for r in ranks]
    return all(b == a + 1 for a, b in zip(idxs, idxs[1:]))

def is_wild(card, level_rank=None, trump_suit=None, wild_cards_enabled=False):
    if not wild_cards_enabled or not level_rank or not trump_suit:
        return False
    parsed = parse_card(card)
    return parsed['rank'] == level_rank and parsed['suit'] == trump_suit

def find_wilds(hand, level_rank, trump_suit, wild_cards_enabled):
    """Return a list of cards in hand that are wilds for this level/trump/wild setting."""
    return [c for c in hand if is_wild(c, level_rank, trump_suit, wild_cards_enabled)]

def card_is_trump(card, level_rank, trump_suit, wild_cards_enabled):
    """A card is trump if:
      - It is a joker
      - OR its suit is the trump suit
      - OR its rank is the level rank
      - OR it is a wild (which means trump_suit + level_rank)
    """
    if card in JOKERS:
        return True
    parsed = parse_card(card)
    if parsed['suit'] == trump_suit:
        return True
    if parsed['rank'] == level_rank:
        return True
    if is_wild(card, level_rank, trump_suit, wild_cards_enabled):
        return True
    return False

def normalize_hand(cards, level_rank=None, trump_suit=None, wild_cards_enabled=False):
    """For move validation, treat wilds as any needed rank/suit except joker."""
    # For basic MVP, treat wilds as the needed rank for hand
    parsed = [parse_card(c) for c in cards]
    # Replace wilds with "assigned" virtual rank (for validation)
    wild_idxs = [i for i, c in enumerate(cards) if is_wild(c, level_rank, trump_suit, wild_cards_enabled)]
    non_wilds = [parse_card(c) for i, c in enumerate(cards) if i not in wild_idxs]

    # Try to assign wilds for each hand type below!
    return parsed  # (for further advanced logic if needed)

def hand_type(cards, level_rank=None, trump_suit=None, wild_cards_enabled=False):
    """Return (type_string, main_rank, extra) or None if invalid"""
    if not cards or len(cards) == 0:
        return None

    ranks = []
    wilds = []
    normal_cards = []
    for c in cards:
        if is_wild(c, level_rank, trump_suit, wild_cards_enabled):
            wilds.append(c)
        else:
            normal_cards.append(c)
            ranks.append(card_rank(c))

    counter = Counter(ranks)
    unique = list(counter.keys())

    # --- Joker Bomb (exactly 2 JoB + 2 JoR)
    if sorted(cards) == ["JoB", "JoB", "JoR", "JoR"]:
        return ("joker_bomb", "JoR", None)

    # --- Bombs (4–10 of a kind, wilds allowed)
    if 4 <= len(cards) <= 10:
        for r in RANK_ORDER[::-1]:
            existing = counter.get(r, 0)
            needed = len(cards) - existing
            if 0 <= needed <= len(wilds):
                return ("bomb", r, "wild" if needed > 0 else None)

    # --- Single
    if len(cards) == 1:
        if len(wilds) == 1:
            return ("single", level_rank, "wild")
        return ("single", ranks[0], None)

    # --- Pair
    if len(cards) == 2:
        if len(wilds) == 2:
            return ("pair", level_rank, "wild")
        elif len(wilds) == 1:
            other_rank = card_rank(normal_cards[0])
            if other_rank == level_rank:
                return ("pair", level_rank, "wild")
        elif len(unique) == 1:
            return ("pair", ranks[0], None)

    # --- Triple
    if len(cards) == 3:
        if len(wilds) > 0 and len(unique) == 1:
            return ("triple", unique[0], "wild")
        elif len(wilds) > 0 and len(unique) == 0:
            return ("triple", level_rank, "wild")
        elif len(unique) == 1 and sum(counter.values()) == 3:
            return ("triple", unique[0], None)

    # --- Full House
    if len(cards) == 5:
        for triple_candidate in RANK_ORDER[::-1]:
            need_triple = 3 - counter.get(triple_candidate, 0)
            if 0 <= need_triple <= len(wilds):
                remaining_wilds = len(wilds) - need_triple
                for pair_candidate in RANK_ORDER:
                    if pair_candidate == triple_candidate:
                        continue
                    need_pair = 2 - counter.get(pair_candidate, 0)
                    if 0 <= need_pair <= remaining_wilds:
                        return ("full_house", triple_candidate, pair_candidate)
    
    # --- Straight Flush
    if len(cards) == 5:
        suits = [card_suit(c) for c in normal_cards if card_rank(c) in RANK_ORDER]
        ranks = [card_rank(c) for c in normal_cards if card_rank(c) in RANK_ORDER]
        wild_count = len(wilds)
        if len(set(suits)) == 1:  # same suit
            for i in range(len(RANK_ORDER) - 4):
                seq = RANK_ORDER[i:i+5]
                missing = [r for r in seq if r not in ranks]
                if len(missing) <= wild_count:
                    return ("straight_flush", seq[-1], None)

    # --- Straight (natural order, 5 cards, wilds can fill gaps)
    if len(cards) == 5:
        candidates = [card_rank(c) for c in normal_cards if c not in JOKERS and card_rank(c) in RANK_ORDER]
        for i in range(len(RANK_ORDER) - 4):
            seq = RANK_ORDER[i:i + 5]
            missing = [r for r in seq if r not in candidates]
            if len(missing) <= len(wilds):
                return ("straight", seq[-1], None)

    # --- Tube: 3 consecutive pairs (6 cards)
    if len(cards) == 6:
        counts = Counter([card_rank(c) for c in normal_cards])
        for i in range(len(RANK_ORDER) - 2):
            seq = RANK_ORDER[i:i + 3]
            needed = sum(max(0, 2 - counts.get(r, 0)) for r in seq)
            if needed <= len(wilds):
                return ("tube", seq[-1], None)

    # --- Plate: 2 consecutive triples (6 cards)
    if len(cards) == 6:
        counts = Counter([card_rank(c) for c in normal_cards])
        for i in range(len(RANK_ORDER) - 1):
            seq = RANK_ORDER[i:i + 2]
            needed = sum(max(0, 3 - counts.get(r, 0)) for r in seq)
            if needed <= len(wilds):
                return ("plate", seq[-1], None)

    return None


def beats(prev, curr, level_rank=None, trump_suit=None, wild_cards_enabled=False):
    """Return True if curr hand beats prev hand, with wild/trump context."""
    if prev is None or prev.get('cards') is None or not prev['cards']:
        return True  # anything can start

    prev_type = hand_type(prev['cards'], level_rank, trump_suit, wild_cards_enabled)
    curr_type = hand_type(curr['cards'], level_rank, trump_suit, wild_cards_enabled)

    if prev_type is None or curr_type is None:
        return False

    bomb_priority = {
        'bomb': 1,
        'straight_flush': 2,
        'joker_bomb': 3
    }

    prev_is_bomb = prev_type[0] in bomb_priority
    curr_is_bomb = curr_type[0] in bomb_priority

    # Joker bomb beats everything
    if curr_type[0] == 'joker_bomb' and prev_type[0] != 'joker_bomb':
        return True

    # Bomb vs non-bomb
    if curr_is_bomb and not prev_is_bomb:
        return True
    if not curr_is_bomb and prev_is_bomb:
        return False

    # Bomb vs bomb: compare type and rank
    if curr_is_bomb and prev_is_bomb:
        prev_rank = bomb_priority[prev_type[0]]
        curr_rank = bomb_priority[curr_type[0]]
        if curr_rank != prev_rank:
            return curr_rank > prev_rank
        else:
            return rank_index(curr_type[1]) > rank_index(prev_type[1])

    # Type mismatch (e.g. straight vs triple)
    if prev_type[0] != curr_type[0] or len(prev['cards']) != len(curr['cards']):
        return False

    # Otherwise compare ranks (including wild handling)
    prev_rank = prev_type[1]
    curr_rank = curr_type[1]
    prev_is_wild = prev_type[-1] == 'wild'
    curr_is_wild = curr_type[-1] == 'wild'

    # Wild beats non-wild, unless opponent is a joker
    if curr_is_wild and not prev_is_wild:
        if prev_rank in ('JoB', 'JoR'):
            return False
        return True
    if not curr_is_wild and prev_is_wild:
        if curr_rank in ('JoB', 'JoR'):
            return True
        return False

    # Compare by natural rank
    return rank_index(curr_rank) > rank_index(prev_rank)

