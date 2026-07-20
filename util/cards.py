import random
from typing import Literal

def get_deck(size: Literal[24, 32, 36, 52, 54], shuffle=False):
    ranks = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
    suits = ['♠', '♥', '♦', '♣']
    include_jokers = False

    match(size):
        case 24:
            from_rank = 7
        case 32:
            from_rank = 7
        case 36:
            from_rank = 7
        case 52:
            from_rank = 7
        case 54:
            from_rank = 7
            include_jokers = True

    deck = [r+s for r in ranks[from_rank:] for s in suits]

    if include_jokers:
        deck += ['Jr', 'Jb']

    if shuffle:
        random.shuffle(deck)
    
    return deck