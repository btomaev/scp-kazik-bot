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
        await msg.answer('Сначала сделай ставку.\n'
                         '/dep xxx')
        return

    result = (await msg.reply_dice(emoji='🎰')).dice
    await user_storage.increment('total_slot_play_count')

    await asyncio.sleep(2)

    if result.value in [1, 22, 43]:
        await user_storage.increment('balance', deposit * 2)
        await user_storage.set('deposit', 0)
        await user_storage.increment('total_wins')
        await user_storage.increment('total_earned', deposit * 2)
        await msg.reply(f'Поздравляю, вы выиграли и ваша ставка удваивается!\n'
                        f'Депозит: {deposit * 2}')
    elif result.value == 64:
        await user_storage.increment('balance', deposit * 10)
        await user_storage.set('deposit', 0)
        await msg.reply(f'Джекпот! Ваша ставка x10!\n'
                        f'Депозит: {deposit * 10}')
    else:
        await user_storage.increment('total_lost', deposit)
        await user_storage.set('deposit', 0)
        await msg.reply(f'Не повезло, твой депозит сгорел.\n'
                        f'Попробуй еще раз, фортуна точно будет на твоей стороне!')


async def dep(msg: types.Message, user_storage: UserStorage):
    if not msg.text:
        await msg.reply('Возвращайся когда у тебя будет что мне предложить')
        return
    
    subject = msg.text.removeprefix('/dep').strip()

    balance = await user_storage.get('balance', default=0) or 0

    if subject.isdecimal():
        value = int(subject)
        if value > balance:
            await msg.reply(f'Ты где-то обсчитался, у тебя всего {balance} на счету')
            return
        if value <= 0:
            await msg.reply('🖕 (с уважением)')
            return
        await user_storage.increment('balance', -value)
        await user_storage.increment('deposit', value)
        await msg.reply(f'Ты депнул: {value}')
        await user_storage.increment('total_deps_count')
    else:
        await msg.reply('Я такое не принимаю')

    
async def loan(msg: types.Message, user_storage: UserStorage):
    last_loan = str(await user_storage.get('last_loan', default='01.01.1991'))
    last_loan = datetime.strptime(last_loan, '%d.%m.%Y')
    now = datetime.now()

    balance = int(await user_storage.get('balance', default=0) or 0)
    deposit = int(await user_storage.get('deposit', default=0) or 0)

    if balance + deposit > 0:
        await msg.answer('У тебя и так есть деньги, иди отсюда, попрошайка.')
        return

    if last_loan.year == now.year and \
       last_loan.month == now.month and \
       last_loan.day == now.day:
        await msg.answer('Я и так занимал тебе сегодня, иди отсюда, лудик несчастный.')

    await user_storage.increment('balance', config.get('loan_value', default=0))
    await user_storage.increment('debt', config.get('loan_value', default=0))
    await user_storage.increment('loans_count')

