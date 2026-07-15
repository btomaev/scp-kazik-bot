import asyncio
from datetime import datetime

from aiogram import types

import config
from storage import UserStorage


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
    deposit = int(await user_storage.get('deposit', default=0) or 0)

    if deposit == 0:
        if msg.text.removeprefix('/slot')
        await msg.answer(config.get('localization.dep.slot.deposit_required'))
        return

    result = (await msg.reply_dice(emoji='🎰')).dice
    await user_storage.increment('total_slot_play_count')

    await asyncio.sleep(2)

    if result.value in [1, 22, 43]:
        await user_storage.increment('balance', deposit * 2)
        await user_storage.set('deposit', 0)
        await user_storage.increment('total_wins')
        await user_storage.increment('total_earned', deposit * 2)
        await msg.reply(
            config.get('localization.dep.slot.win').format(
                deposit=deposit * 5,
            )
        )
    elif result.value == 64:
        await user_storage.increment('balance', deposit * 10)
        await user_storage.set('deposit', 0)
        await msg.reply(
            config.get('localization.dep.slot.jackpot').format(
                deposit=deposit * 10,
            )
        )
    else:
        await user_storage.increment('total_lost', deposit)
        await user_storage.set('deposit', 0)
        await msg.reply(config.get('localization.dep.slot.loss'))


async def dep(msg: types.Message, user_storage: UserStorage):
    if not msg.text:
        await msg.reply(config.get('localization.dep.empty_subject'))
        return
    
    subject = msg.text.removeprefix('/dep').strip()

    balance = await user_storage.get('balance', default=0) or 0

    if subject.isdecimal():
        value = int(subject)
        if value > balance:
            await msg.reply(
                config.get('localization.dep.insufficient_balance').format(
                    balance=balance,
                )
            )
            return
        if value <= 0:
            await msg.reply(config.get('localization.dep.non_positive_value'))
            return
        await user_storage.increment('balance', -value)
        await user_storage.increment('deposit', value)
        await msg.reply(
            config.get('localization.dep.accepted').format(value=value)
        )
        await user_storage.increment('total_deps_count')
    else:
        await msg.reply(config.get('localization.dep.invalid_subject'))

    
async def loan(msg: types.Message, user_storage: UserStorage):
    last_loan = str(await user_storage.get('last_loan', default='01.01.1991'))
    last_loan = datetime.strptime(last_loan, '%d.%m.%Y')
    now = datetime.now()

    balance = int(await user_storage.get('balance', default=0) or 0)
    deposit = int(await user_storage.get('deposit', default=0) or 0)

    if balance + deposit > 0:
        await msg.answer(config.get('localization.dep.loan.funds_available'))
        return

    if last_loan.year == now.year and \
       last_loan.month == now.month and \
       last_loan.day == now.day:
        await msg.answer(config.get('localization.dep.loan.already_received'))

    loan_value = config.get('loan_value', default=0)

    await user_storage.increment('balance', loan_value)
    await user_storage.increment('debt', loan_value)
    await user_storage.increment('loans_count')
    await user_storage.set('last_loan', now.strftime('%d.%m.%Y'))

    await msg.answer(
        config.get('localization.dep.loan.received').format(
            loan_value=loan_value,
        )
    )
