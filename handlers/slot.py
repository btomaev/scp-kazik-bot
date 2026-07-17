import asyncio

from aiogram import types

import config
from handlers.dep import place_bet
from storage import UserStorage
from util.msgtools import remove_command_prefix


# async def slot(msg: types.Message):
#     stream = build_slot_tgs(randint(0, 5), randint(0, 5), randint(0, 5))
#     sticker = types.BufferedInputFile(
#         stream.getvalue(),
#         filename=stream.name,
#     )

#     await msg.reply_sticker(
#         sticker=sticker,
#         emoji="🎰",
#     )


async def slot(msg: types.Message, user_storage: UserStorage):
    subject = remove_command_prefix(msg.text)
    if subject and not await place_bet(msg, user_storage, subject):
        return

    deposit = await user_storage.get('deposit', default=0) or 0
    if deposit == 0:
        await msg.answer(config.get('localization.dep.slot.deposit_required'))
        return

    result = (await msg.reply_dice(emoji='🎰')).dice
    await user_storage.increment('total_slot_play_count')

    await asyncio.sleep(2)

    if result.value in [1, 22, 43]:
        await user_storage.increment('balance', deposit * 5)
        await user_storage.set('deposit', 0)
        await user_storage.increment('total_slot_wins')
        await user_storage.increment('total_slot_earned', deposit * 5)
        await msg.reply(
            config.get('localization.dep.slot.win').format(
                deposit=deposit * 5,
            )
        )
    elif result.value == 64:
        await user_storage.increment('balance', deposit * 10)
        await user_storage.set('deposit', 0)
        await user_storage.increment('total_slot_wins')
        await user_storage.increment('total_slot_earned', deposit * 5)
        await msg.reply(
            config.get('localization.dep.slot.jackpot').format(
                deposit=deposit * 10,
            )
        )
    else:
        await user_storage.increment('total_slot_lost', deposit)
        await user_storage.set('deposit', 0)
        await msg.reply(config.get('localization.dep.slot.loss'))
