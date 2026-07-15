from aiogram import types

import config
from storage import UserStorage


async def start(msg: types.Message, user_storage: UserStorage):
    is_first_time = not await user_storage.get('is_seen')

    if is_first_time:
        start_balance = config.get('start_balance', default=0)
        await user_storage.set_many({
            'balance': start_balance,
            'is_seen': True
        })
        await msg.reply(
            config.get('localization.start.welcome').format(
                start_balance=start_balance,
            )
        )
    
