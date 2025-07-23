
import pytest
from game.hands import hand_type, beats

LEVEL = "7"
TRUMP = "hearts"
WILD = True

# === Singles ===
def test_single_normal():
    assert hand_type(["5H"], LEVEL, TRUMP, WILD) == ("single", "5", None)

def test_single_wild():
    assert hand_type(["7H"], LEVEL, TRUMP, WILD) == ("single", "7", "wild")

# === Pairs ===
def test_pair_normal():
    assert hand_type(["8H", "8D"], LEVEL, TRUMP, WILD) == ("pair", "8", None)

def test_pair_double_wild():
    assert hand_type(["7H", "7H"], LEVEL, TRUMP, WILD) == ("pair", "7", "wild")

def test_pair_one_wild():
    assert hand_type(["7H", "7S"], LEVEL, TRUMP, WILD) == ("pair", "7", "wild")

# === Triples ===
def test_triple_all_same():
    assert hand_type(["9H", "9S", "9C"], LEVEL, TRUMP, WILD) == ("triple", "9", None)

def test_triple_with_one_wild():
    assert hand_type(["9H", "9S", "7H"], LEVEL, TRUMP, WILD) == ("triple", "9", "wild")

def test_triple_with_two_wilds():
    assert hand_type(["9H", "7H", "7H"], LEVEL, TRUMP, WILD) == ("triple", "9", "wild")

# === Full House ===
def test_full_house_with_wild():
    cards = ["7H", "8H", "8D", "8S", "9H"]
    assert hand_type(cards, LEVEL, TRUMP, WILD) == ("full_house", "8", "9")

# === Straight ===
def test_straight_with_wild():
    cards = ["3H", "4H", "6D", "7H", "7H"]
    assert hand_type(cards, LEVEL, TRUMP, WILD) == ("straight", "7", None)

def test_straight_with_2_wilds():
    cards = ["4H", "7H", "7H", "5D", "6S"]
    assert hand_type(cards, LEVEL, TRUMP, WILD) == ("straight", "7", None)

# === Tube ===
def test_tube_with_wild():
    cards = ["4H", "4D", "5S", "5C", "6D", "7H"]
    assert hand_type(cards, LEVEL, TRUMP, WILD) == ("tube", "6", None)

def test_tube_with_2_wilds():
    cards = ["5H", "6H", "7H", "7H", "4S", "4D"]
    assert hand_type(cards, LEVEL, TRUMP, WILD) == ("tube", "6", None)

# === Plate ===
def test_plate_with_wild():
    cards = ["8S", "8D", "8C", "9H", "9S", "7H"]
    assert hand_type(cards, LEVEL, TRUMP, WILD) == ("plate", "9", None)

def test_plate_with_2_wilds():
    cards = ["4H", "4D", "5H", "7H", "7H", "5C"]
    assert hand_type(cards, LEVEL, TRUMP, WILD) == ("tube", "5", None)

# === Joker Bomb ===
def test_joker_bomb():
    assert hand_type(["JoB", "JoB", "JoR", "JoR"], LEVEL, TRUMP, WILD) == ("joker_bomb", "JoR", None)

def test_joker_bomb_with_wild_should_fail():
    assert hand_type(["JoB", "JoB", "JoR", "7H"], LEVEL, TRUMP, WILD) is None

def test_joker_bomb_with_extra_card_should_fail():
    assert hand_type(["JoB", "JoB", "JoR", "JoR", "7H"], LEVEL, TRUMP, WILD) is None

def test_joker_bomb_with_less_than_4_cards():
    assert hand_type(["JoR", "JoR", "JoB"], LEVEL, TRUMP, WILD) is None

# === Bombs ===
def test_quad_bomb():
    assert hand_type(["6H", "6S", "6D", "6C"], LEVEL, TRUMP, WILD) == ("bomb", "6", None)

def test_quintuple_bomb_with_wild():
    assert hand_type(["7H", "7S", "7D", "7C", "7H"], LEVEL, TRUMP, WILD) == ("bomb", "7", "wild")

# === Beats tests ===
def test_wild_single_beats_ace():
    prev = {"player": "A", "cards": ["AH"]}
    curr = {"player": "B", "cards": ["7H"]}
    assert beats(prev, curr, LEVEL, TRUMP, WILD) is True

def test_bomb_beats_pair():
    prev = {"player": "A", "cards": ["6S", "6H"]}
    curr = {"player": "B", "cards": ["7H", "7S", "7D", "7C"]}
    assert beats(prev, curr, LEVEL, TRUMP, WILD) is True

def test_bomb_beats_lower_bomb():
    bomb1 = {"player": "A", "cards": ["6H", "6S", "6D", "6C"]}
    bomb2 = {"player": "B", "cards": ["7H", "7S", "7D", "7C"]}
    assert beats(bomb1, bomb2, LEVEL, TRUMP, WILD) is True

def test_straight_flush_beats_quad_bomb():
    straight_flush = ["9H", "10H", "JH", "QH", "KH"]
    bomb = ["5S", "5H", "5D", "5C"]
    assert beats({"player": "A", "cards": bomb}, {"player": "B", "cards": straight_flush}, LEVEL, TRUMP, WILD) is True

def test_four_joker_beats_all():
    normal_bomb = {"player": "A", "cards": ["AS", "AH", "AD", "AC"]}
    joker_bomb = {"player": "B", "cards": ["JoR", "JoR", "JoB", "JoB"]}
    assert beats(normal_bomb, joker_bomb, LEVEL, TRUMP, WILD) is True

# === Joker rejection in straights ===
def test_straight_with_joker_should_fail():
    cards = ["3H", "4H", "JoB", "6H", "7H"]
    assert hand_type(cards, LEVEL, TRUMP, WILD) is None

def test_straight_flush_with_joker_should_fail():
    cards = ["9H", "10H", "JH", "JoR", "QH"]
    assert hand_type(cards, LEVEL, TRUMP, WILD) is None
