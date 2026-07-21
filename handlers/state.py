from typing import Any

from aiogram import types

import config
from storage import UserStorage


def _counter(value: Any) -> int:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return 0
    return max(0, int(value))


def _win_rate(wins: int, games: int) -> str:
    if games <= 0:
        return '0.0'
    return f'{wins / games * 100:.1f}'


async def balance(msg: types.Message, user_storage: UserStorage):
    balance = await user_storage.get('balance', default=0)
    deposit = await user_storage.get('deposit', default=0)
    debt = await user_storage.get('debt', default=0)

    await msg.reply(
        config.get('localization.state.balance').format(
            balance=balance,
            deposit=deposit,
            debt=debt,
        )
    )


async def stats(msg: types.Message, user_storage: UserStorage):
    values = await user_storage.all()

    total_slot_play = _counter(values.get('total_slot_play_count'))
    total_slot_wins = _counter(values.get('total_slot_wins'))
    total_slot_losses = max(0, total_slot_play - total_slot_wins)
    total_slot_earned = _counter(values.get('total_slot_earned'))
    total_slot_lost = _counter(values.get('total_slot_lost'))

    blackjack_stats = values.get('blackjack_stats')
    if not isinstance(blackjack_stats, dict):
        blackjack_stats = {}

    total_blackjack_play = _counter(blackjack_stats.get('played'))
    total_blackjack_wins = _counter(blackjack_stats.get('wins'))
    total_blackjack_losses = _counter(blackjack_stats.get('losses'))
    total_blackjack_pushes = _counter(blackjack_stats.get('pushes'))
    total_blackjacks = _counter(blackjack_stats.get('blackjacks'))

    total_play = total_slot_play + total_blackjack_play
    total_wins = total_slot_wins + total_blackjack_wins
    total_losses = total_slot_losses + total_blackjack_losses
    total_pushes = total_blackjack_pushes

    await msg.reply(
        config.get('localization.state.stats').format(
            total_play=total_play,
            total_wins=total_wins,
            total_losses=total_losses,
            total_pushes=total_pushes,
            total_win_rate=_win_rate(total_wins, total_play),
            total_slot_lost=total_slot_lost,
            total_slot_earned=total_slot_earned,
            total_slot_wins=total_slot_wins,
            total_slot_losses=total_slot_losses,
            total_slot_play=total_slot_play,
            total_slot_win_rate=_win_rate(total_slot_wins, total_slot_play),
            total_blackjack_play=total_blackjack_play,
            total_blackjack_wins=total_blackjack_wins,
            total_blackjack_losses=total_blackjack_losses,
            total_blackjack_pushes=total_blackjack_pushes,
            total_blackjacks=total_blackjacks,
            total_blackjack_win_rate=_win_rate(
                total_blackjack_wins,
                total_blackjack_play,
            ),
        )
    )
