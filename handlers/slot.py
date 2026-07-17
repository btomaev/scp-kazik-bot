import asyncio

from aiogram import types
from aiogram.exceptions import TelegramRetryAfter

import config
from storage import UserStorage
from util.msgtools import parse_int, remove_command_prefix


async def slot(msg: types.Message, user_storage: UserStorage):
    subject = remove_command_prefix(msg.text)
    if subject:
        deposit, _ = parse_int(subject)
        if deposit <= 0:
            await msg.answer(config.get('localization.dep.non_positive_value'))
            return
    else:
        deposit = await user_storage.get('deposit', default=0) or 0

    if deposit == 0:
        await msg.answer(config.get('localization.dep.slot.deposit_required'))
        return
    
    balance = await user_storage.get('balance', default=0) or 0
    if deposit > balance:
        await msg.answer(config.get('localization.dep.insufficient_balance').format(
            balance=balance
        ))
        return
    
    await user_storage.increment('total_slot_play_count')
    await user_storage.increment('balance', -deposit)

    try:
        result = (await msg.reply_dice(emoji='🎰')).dice
    except TelegramRetryAfter:
        await msg.reply(config.get('localization.system.too_many_stickers'))
        return

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
