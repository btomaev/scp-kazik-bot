import asyncio

from aiogram import types

import config
from storage import UserStorage
from util.msgtools import parse_int, remove_command_prefix


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
    if subject:
        value, _ = parse_int(subject)
        balance = await user_storage.get('balance', default=0) or 0
        if value <= balance:
            deposit = value
        else:
            await msg.answer(config.get('localization.dep.insufficient_balance').format(
                balance=balance
            ))
            return
    else:
        deposit = await user_storage.get('deposit', default=0) or 0

    if deposit == 0:
        await msg.answer(config.get('localization.dep.slot.deposit_required'))
        return
    
    await user_storage.increment('total_slot_play_count')
    await user_storage.increment('balance', -deposit)

    result = (await msg.reply_dice(emoji='🎰')).dice

    await asyncio.sleep(2)

    if not result:
        await msg.reply(config.get('localization.system.critical_error'))
        return

    if result.value in [1, 22, 43]:
        gesheft = deposit * 5
        await user_storage.increment('balance', gesheft)
        await user_storage.increment('total_slot_wins')
        await user_storage.increment('total_slot_earned', gesheft)
        await msg.reply(
            config.get('localization.dep.slot.win').format(
                deposit=gesheft,
            )
        )
    elif result.value == 64:
        gesheft = deposit * 10
        await user_storage.increment('balance', gesheft)
        await user_storage.increment('total_slot_wins')
        await user_storage.increment('total_slot_earned', gesheft)
        await msg.reply(
            config.get('localization.dep.slot.jackpot').format(
                deposit=gesheft,
            )
        )
    else:
        await user_storage.increment('total_slot_lost', deposit)
        await msg.reply(config.get('localization.dep.slot.loss'))
