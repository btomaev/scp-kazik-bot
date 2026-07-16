from datetime import datetime
from aiogram import types

import config
from storage import UserStorage
from util.msgtools import remove_command_prefix


async def place_bet(
    msg: types.Message,
    user_storage: UserStorage,
    subject: str,
) -> int | None:
    balance = await user_storage.get('balance', default=0) or 0

    if not subject.isdecimal():
        await msg.reply(config.get('localization.dep.invalid_subject'))
        return

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
    await user_storage.increment('total_deps_count')
    return value


async def dep(msg: types.Message, user_storage: UserStorage):
    if not msg.text:
        await msg.reply(config.get('localization.dep.empty_subject'))
        return

    subject = remove_command_prefix(msg.text)
    value = await place_bet(msg, user_storage, subject)
    if value:
        deposit = await user_storage.get('deposit', default=0) or 0
        await msg.reply(
            config.get('localization.dep.accepted').format(value=deposit),
            allow_sending_without_reply=True
        )


async def loan(msg: types.Message, user_storage: UserStorage):
    last_loan = str(await user_storage.get('last_loan', default='01.01.1991'))
    last_loan = datetime.strptime(last_loan, '%d.%m.%Y')
    now = datetime.now()

    balance = await user_storage.get('balance', default=0) or 0
    deposit = await user_storage.get('deposit', default=0) or 0

    if balance + deposit > 0:
        await msg.answer(config.get('localization.dep.loan.funds_available'))
        return

    if last_loan.year == now.year and \
       last_loan.month == now.month and \
       last_loan.day == now.day:
        await msg.answer(config.get('localization.dep.loan.already_received'))
        return

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
