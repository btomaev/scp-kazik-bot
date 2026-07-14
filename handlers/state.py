from aiogram import types
from storage import UserStorage


async def balance(msg: types.Message, user_storage: UserStorage):
    balance = await user_storage.get('balance', default=0)
    deposit = await user_storage.get('deposit', default=0)
    debt = await user_storage.get('debt', default=0)

    await msg.reply(f'Твой баланс: {balance}\n'
                    f'Ты депнул: {deposit}\n'
                    f'Твой долг: {debt}')


async def stats(msg: types.Message, user_storage: UserStorage):
    total_deps = await user_storage.get('total_deps_count', default=0)
    total_lost = await user_storage.get('total_lost', default=0)
    total_earned = await user_storage.get('total_earned', default=0)
    total_wins = await user_storage.get('total_wins', default=0)
    total_slot_play = await user_storage.get('total_slot_play_count', default=0)

    await msg.reply(f'Всего депов: {total_deps}\n'
                    f'Пролудоманенно: {total_lost}\n'
                    f'Сыграно в слотмашину: {total_slot_play}')
