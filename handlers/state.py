from aiogram import types

import config
from storage import UserStorage


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
    total_slot_lost = await user_storage.get('total_slot_lost', default=0)
    total_slot_earned = await user_storage.get('total_earned', default=0)
    total_slot_wins = await user_storage.get('total_wins', default=0)
    total_slot_play = await user_storage.get('total_slot_play_count', default=0)

    total_lost = total_slot_lost
    total_earned = total_slot_earned
    total_wins = total_slot_wins

    await msg.reply(
        config.get('localization.state.stats').format(
            total_wins=total_wins,
            total_lost=total_lost,
            total_earned=total_earned,
            total_slot_wins=total_slot_wins,
            total_slot_play=total_slot_play,
        )
    )
