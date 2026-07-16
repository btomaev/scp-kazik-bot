from aiogram import types

import config
from storage import BotStorage, PersistentStorage
from util.msgtools import parse_int, remove_command_prefix


async def admit_chat(msg: types.Message, bot_storage: BotStorage):
    if msg.from_user and msg.from_user.id != int(config.get('admin')):
        return

    await bot_storage.mutate(
        "admitted_chats",
        lambda admitted_chats: admitted_chats if msg.chat in admitted_chats else [*admitted_chats, msg.chat],
        default=[],
    )

    await msg.reply(config.get('localization.admin.chat_admitted'))


async def deny_chat(msg: types.Message, bot_storage: BotStorage):
    if msg.from_user and msg.from_user.id != int(config.get('admin')):
        return

    await bot_storage.mutate(
        "admitted_chats",
        lambda admitted_chats: [c for c in admitted_chats if c != msg.chat],
        default=[],
    )

    await msg.reply(config.get('localization.admin.chat_denied'))


async def set_balance(msg: types.Message, storage: PersistentStorage):
    if msg.from_user and msg.from_user.id != int(config.get('admin')):
        return
    
    text = remove_command_prefix(msg.text)
    value, _ = parse_int(text)
    value = max(value, 0)

    replied = msg.reply_to_message
    if replied is None or replied.from_user is None:
        await msg.reply(config.get('localization.admin.insufficient_reply'))
        return

    target_storage = storage.for_user(replied.from_user.id)
    await target_storage.set('balance', value)
    await msg.reply(config.get('localization.admin.set_balance_successful'))


async def change_balance(msg: types.Message, storage: PersistentStorage):
    if msg.from_user and msg.from_user.id != int(config.get('admin')):
        return
    
    text = remove_command_prefix(msg.text)
    value, _ = parse_int(text)

    replied = msg.reply_to_message
    if replied is None or replied.from_user is None:
        await msg.reply(config.get('localization.admin.insufficient_reply'))
        return

    target_storage = storage.for_user(replied.from_user.id)
    await target_storage.increment('balance', value)
    await msg.reply(config.get('localization.admin.set_balance_successful'))


async def set_debt(msg: types.Message, storage: PersistentStorage):
    if msg.from_user and msg.from_user.id != int(config.get('admin')):
        return
    
    text = remove_command_prefix(msg.text)
    value, _ = parse_int(text)
    value = max(value, 0)

    replied = msg.reply_to_message
    if replied is None or replied.from_user is None:
        await msg.reply(config.get('localization.admin.insufficient_reply'))
        return

    target_storage = storage.for_user(replied.from_user.id)
    await target_storage.set('balance', value)
    await msg.reply(config.get('localization.admin.set_debt_successful'))
