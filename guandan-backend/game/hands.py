from collections import Counter

RANK_ORDER = ['3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A', '2']
JOKERS = ['JoB', 'JoR']

def card_rank(card):
    if card in JOKERS:
        return card
    return card[:-1] if not card.startswith("Jo") else card

def rank_index(rank):
    if rank in JOKERS:
        return 100 + JOKERS.index(rank)  # always highest
    return RANK_ORDER.index(rank)

def is_consecutive(ranks):
    """Are all given (sorted) ranks consecutive in RANK_ORDER?"""
    idxs = [rank_index(r) for r in ranks]
    return all(b == a + 1 for a, b in zip(idxs, idxs[1:]))

def hand_type(cards):
    """Return (type_string, main_rank, extra) or None if invalid"""
    cards = list(cards)
    if len(cards) == 0:
        return None
    ranks = [card_rank(c) for c in cards]
    counter = Counter(ranks)
    unique = list(counter.keys())

    # Joker Bomb
    if set(cards) == set(JOKERS) and len(cards) == 2:
        return ('joker_bomb', 'JoR', None)

    # Bomb
    if len(cards) == 4 and len(unique) == 1:
        return ('bomb', unique[0], None)

    # Single
    if len(cards) == 1:
        return ('single', ranks[0], None)

    # Pair
    if len(cards) == 2 and len(unique) == 1:
        return ('pair', ranks[0], None)

    # Triple
    if len(cards) == 3 and len(unique) == 1:
        return ('triple', ranks[0], None)

    # Full House (3+2)
    if len(cards) == 5 and set(counter.values()) == {3,2}:
        triple_rank = [r for r, c in counter.items() if c == 3][0]
        pair_rank = [r for r, c in counter.items() if c == 2][0]
        return ('full_house', triple_rank, pair_rank)

    # Straight (5 cards, not including jokers or 2s, all unique, consecutive)
    if len(cards) == 5 and all(r in RANK_ORDER for r in ranks) and len(unique) == 5:
        sorted_ranks = sorted(ranks, key=rank_index)
        if is_consecutive(sorted_ranks):
            return ('straight', sorted_ranks[-1], None)

    # Tube: Three consecutive pairs (6 cards: aa bb cc, all unique, each count==2)
    if len(cards) == 6 and all(v == 2 for v in counter.values()) and len(unique) == 3:
        sorted_ranks = sorted(unique, key=rank_index)
        if is_consecutive(sorted_ranks):
            return ('tube', sorted_ranks[-1], None)

    # Plate: Two consecutive triples (6 cards: aaa bbb, all unique, each count==3)
    if len(cards) == 6 and all(v == 3 for v in counter.values()) and len(unique) == 2:
        sorted_ranks = sorted(unique, key=rank_index)
        if is_consecutive(sorted_ranks):
            return ('plate', sorted_ranks[-1], None)

    # Not a valid hand type
    return None

def beats(prev, curr):
    """Return True if curr hand beats prev hand"""
    if prev is None or prev.get('cards') is None or not prev['cards']:
        return True  # anything can start

    prev_type = hand_type(prev['cards'])
    curr_type = hand_type(curr['cards'])
    if prev_type is None or curr_type is None:
        return False

    # Joker bomb always beats everything (except same)
    if curr_type[0] == 'joker_bomb':
        if prev_type[0] != 'joker_bomb':
            return True
        # If both are joker bomb, cannot beat unless played second (no point)

    # Bomb beats everything except a higher bomb or joker bomb
    if curr_type[0] == 'bomb':
        if prev_type[0] != 'bomb' and prev_type[0] != 'joker_bomb':
            return True
        if prev_type[0] == 'bomb':
            # Compare rank
            return rank_index(curr_type[1]) > rank_index(prev_type[1])

    # Otherwise, must match type and length
    if prev_type[0] != curr_type[0] or len(prev['cards']) != len(curr['cards']):
        return False

    # Compare main rank
    return rank_index(curr_type[1]) > rank_index(prev_type[1])
