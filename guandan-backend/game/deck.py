import random

# Basic 54-card deck (standard + jokers) for example — expand as needed
SUITS = ['S', 'H', 'D', 'C']
RANKS = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
JOKERS = ['JoR', 'JoB']  # Red Joker, Black Joker

def create_deck():
    deck = [rank + suit for suit in SUITS for rank in RANKS]
    deck += JOKERS * 2  # 2 red jokers and 2 black jokers total
    return deck

def shuffle_deck(deck):
    random.shuffle(deck)

def deal_cards(deck, num_players=4):
    """Deal cards evenly to num_players, return list of hands."""
    hands = [[] for _ in range(num_players)]
    for i, card in enumerate(deck):
        hands[i % num_players].append(card)
    return hands
