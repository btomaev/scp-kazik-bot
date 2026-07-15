from aiogram import types

import config
from storage import BotStorage


async def admit_chat(msg: types.Message, bot_storage: BotStorage):
    if msg.from_user != config.get('admin'):
        return

    await bot_storage.mutate(
        "admitted_chats",
        lambda admitted_chats: admitted_chats if msg.chat in admitted_chats else [*admitted_chats, msg.chat],
        default=[],
    )

    await msg.reply(config.get('localization.admin.chat_admitted'))


async def deny_chat(msg: types.Message, bot_storage: BotStorage):
    if msg.from_user != config.get('admin'):
        return

    await bot_storage.mutate(
        "admitted_chats",
        lambda admitted_chats: [c for c in admitted_chats if c != msg.chat],
        default=[],
    )

    await msg.reply(config.get('localization.admin.chat_denied'))
