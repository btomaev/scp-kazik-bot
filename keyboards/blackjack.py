from typing import Literal

from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

import config


class BlackjackCallback(CallbackData, prefix='blackjack'):
    action: Literal['create', 'start', 'join', 'exit', 'controls', 'hit', 'stand']
    room_id: str = ''


def make_room_keyboard(owner_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text=config.get('localization.rooms.make_btn'),
        callback_data=BlackjackCallback(action='create', room_id=str(owner_id)),
    )
    return builder.as_markup()


def waiting_room_keyboard(
    room_id: str,
    joined_players: int,
    max_players: int,
    can_start: bool = False,
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text=config.get('localization.rooms.join_btn').format(
            joined_players=joined_players,
            max_players=max_players,
        ),
        callback_data=BlackjackCallback(action='join', room_id=room_id),
    )
    builder.button(
        text=config.get('localization.rooms.exit_btn'),
        callback_data=BlackjackCallback(action='exit', room_id=room_id),
    )
    if can_start:
        builder.button(
            text=config.get('localization.rooms.start_btn'),
            callback_data=BlackjackCallback(action='start', room_id=room_id),
        )
    builder.adjust(1)
    return builder.as_markup()


def table_room_keyboard(room_id: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text=config.get('localization.blackjack.playtime.controls_btn'),
        callback_data=BlackjackCallback(action='controls', room_id=room_id),
    )
    return builder.as_markup()


def active_room_keyboard(
    room_id: str,
    can_hit: bool = False,
    can_stand: bool = False,
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if can_hit:
        builder.button(
            text=config.get('localization.blackjack.playtime.hit_btn'),
            callback_data=BlackjackCallback(action='hit', room_id=room_id),
        )
    if can_stand:
        builder.button(
            text=config.get('localization.blackjack.playtime.stand_btn'),
            callback_data=BlackjackCallback(action='stand', room_id=room_id),
        )
    builder.adjust(1)
    return builder.as_markup()
