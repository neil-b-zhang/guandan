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
    """Return (type_string, main_rank, extra) or None if invalid
       For wild MVP: only allow wilds to act as missing rank in a combo (e.g. 5♥ 6♥ [7♥ wild] 8♥ 9♥ is a straight)
       - If wild is played as single or pair, counts as level rank (ranks above A, below JoB)
    """
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

    # Joker Bomb
    if set(cards) == set(JOKERS) and len(cards) == 2:
        return ('joker_bomb', 'JoR', None)

    # Bomb (four of a kind, no wilds allowed)
    if len(cards) == 4 and len(wilds) == 0 and len(unique) == 1:
        return ('bomb', unique[0], None)

    # Single (wild as level rank)
    if len(cards) == 1:
        if len(wilds) == 1:
            return ('single', level_rank, 'wild')
        return ('single', ranks[0], None)

    # Pair (wilds allowed only as both wild or wild + real level card)
    if len(cards) == 2:
        if len(wilds) == 2:
            return ('pair', level_rank, 'wild')
        elif len(wilds) == 1:
            # If other is level_rank
            other_rank = card_rank(normal_cards[0])
            if other_rank == level_rank:
                return ('pair', level_rank, 'wild')
        elif len(unique) == 1:
            return ('pair', ranks[0], None)

    # Triple (wilds allowed if missing one/two)
    if len(cards) == 3:
        if len(wilds) + len(unique) == 1:
            return ('triple', unique[0] if unique else level_rank, 'wild')
        elif len(unique) == 1 and sum(counter.values()) + len(wilds) == 3:
            return ('triple', unique[0], None)

    # Full House (3+2, wilds can fill any)
    if len(cards) == 5:
        for triple_candidate in RANK_ORDER[::-1]:
            needed_for_triple = 3 - counter.get(triple_candidate, 0)
            if 0 <= needed_for_triple <= len(wilds):
                # Remaining wilds try to make a pair
                left_wilds = len(wilds) - needed_for_triple
                pair_ranks = [r for r in RANK_ORDER if r != triple_candidate]
                for pair_candidate in pair_ranks:
                    needed_for_pair = 2 - counter.get(pair_candidate, 0)
                    if needed_for_pair == left_wilds:
                        return ('full_house', triple_candidate, pair_candidate)
        # No valid full house using wilds
    # Straight (5 cards, wilds can fill gaps, but cannot use jokers, cannot wrap around)
    if len(cards) == 5:
        candidates = [card_rank(c) for c in normal_cards if c not in JOKERS and card_rank(c) in RANK_ORDER]
        # Try every possible 5-card window
        for i in range(len(RANK_ORDER)-4):
            seq = RANK_ORDER[i:i+5]
            missing = [r for r in seq if r not in candidates]
            if len(missing) <= len(wilds):
                # All cards present or can fill with wilds
                return ('straight', seq[-1], None)
    # Tube: Three consecutive pairs (6 cards)
    if len(cards) == 6:
        # Count pairs (wilds can fill gaps)
        counts = Counter([card_rank(c) for c in normal_cards])
        possible = []
        for i in range(len(RANK_ORDER)-2):
            seq = RANK_ORDER[i:i+3]
            needed = 0
            for r in seq:
                needed += max(0, 2 - counts.get(r,0))
            if needed <= len(wilds):
                possible.append(seq[-1])
        if possible:
            return ('tube', possible[-1], None)
    # Plate: Two consecutive triples (6 cards)
    if len(cards) == 6:
        counts = Counter([card_rank(c) for c in normal_cards])
        possible = []
        for i in range(len(RANK_ORDER)-1):
            seq = RANK_ORDER[i:i+2]
            needed = 0
            for r in seq:
                needed += max(0, 3 - counts.get(r,0))
            if needed <= len(wilds):
                possible.append(seq[-1])
        if possible:
            return ('plate', possible[-1], None)

    return None

def beats(prev, curr, level_rank=None, trump_suit=None, wild_cards_enabled=False):
    """Return True if curr hand beats prev hand, with wild/trump context."""
    if prev is None or prev.get('cards') is None or not prev['cards']:
        return True  # anything can start
    prev_type = hand_type(prev['cards'], level_rank, trump_suit, wild_cards_enabled)
    curr_type = hand_type(curr['cards'], level_rank, trump_suit, wild_cards_enabled)
    if prev_type is None or curr_type is None:
        return False
    # Joker bomb always beats everything except another joker bomb
    if curr_type[0] == 'joker_bomb':
        if prev_type[0] != 'joker_bomb':
            return True
    # Bomb beats everything except higher bomb or joker bomb
    if curr_type[0] == 'bomb':
        if prev_type[0] != 'bomb' and prev_type[0] != 'joker_bomb':
            return True
        if prev_type[0] == 'bomb':
            return rank_index(curr_type[1]) > rank_index(prev_type[1])
    # Otherwise, must match type and length
    if prev_type[0] != curr_type[0] or len(prev['cards']) != len(curr['cards']):
        return False
    # Compare rank (special: wild pair is always higher than ace but below JoB)
    prev_rank = prev_type[1]
    curr_rank = curr_type[1]
    prev_is_wild = prev_type[-1] == 'wild'
    curr_is_wild = curr_type[-1] == 'wild'
    # Wild singles/pairs always rank above ace but below black joker
    if curr_is_wild and not prev_is_wild:
        if prev_rank == 'A':
            return True
        elif prev_rank == 'JoB' or prev_rank == 'JoR':
            return False
    if not curr_is_wild and prev_is_wild:
        if curr_rank == 'A':
            return False
        elif curr_rank == 'JoB' or curr_rank == 'JoR':
            return True
    # Otherwise compare by normal order
    return rank_index(curr_rank) > rank_index(prev_rank)
