from typing import Literal

from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

import config


class BlackjackCallback(CallbackData, prefix='blackjack'):
    action: Literal['create', 'start', 'join', 'exit']
    room_id: str = ''


def make_room_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text=config.get('localization.rooms.make_btn',),
        callback_data=BlackjackCallback(action='create'),
    )
    return builder.as_markup()


def waiting_room_keyboard(
    room_id: str,
    joined_players: int,
    max_players: int,
    can_start: bool=False,
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    builder.button(
        text=config.get(
            'localization.rooms.join_btn',
        ).format(
            joined_players=joined_players,
            max_players=max_players,
        ),
        callback_data=BlackjackCallback(
            action='join',
            room_id=room_id,
        ),
    )

    builder.button(
        text=config.get(
            'localization.rooms.exit_btn',
        ).format(
            joined_players=joined_players,
            max_players=max_players,
        ),
        callback_data=BlackjackCallback(
            action='exit',
            room_id=room_id,
        ),
    )

    if can_start:
        builder.button(
            text=config.get(
                'localization.rooms.start_btn',
            ).format(
                joined_players=joined_players,
                max_players=max_players,
            ),
            callback_data=BlackjackCallback(
                action='start',
                room_id=room_id,
            ),
        )

    builder.adjust(1)
    return builder.as_markup()