import random
from typing import Literal

def get_deck(size: Literal[24, 32, 36, 52, 54], shuffle=False):
    ranks = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
    suits = ['♠', '♥', '♦', '♣']
    first_rank_by_size = {
        24: 7,
        32: 5,
        36: 4,
        52: 0,
        54: 0,
    }
    if size not in first_rank_by_size:
        raise ValueError(f'unsupported deck size: {size}')

    from_rank = first_rank_by_size[size]
    include_jokers = size == 54

    deck = [r+s for r in ranks[from_rank:] for s in suits]

    if include_jokers:
        deck += ['Jr', 'Jb']

    if shuffle:
        random.shuffle(deck)
    
    return deck
