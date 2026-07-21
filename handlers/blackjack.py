import asyncio
import html
import secrets
from collections.abc import Sequence
from typing import Any

from aiogram import exceptions, types

import config
from keyboards.blackjack import (
    BlackjackCallback,
    active_room_keyboard,
    make_room_keyboard,
    table_room_keyboard,
    waiting_room_keyboard,
)
from storage import BotStorage, PersistentStorage
from util.cards import get_deck


Room = dict[str, Any]
Player = dict[str, Any]


class BlackjackActionError(Exception):
    def __init__(self, localization_key: str):
        super().__init__(localization_key)
        self.localization_key = localization_key


async def blackjack(msg: types.Message):
    if not msg.from_user:
        return

    text = config.get('localization.blackjack.room.make')
    markup = make_room_keyboard(msg.from_user.id)
    send_options: dict[str, Any] = {
        'chat_id': msg.chat.id,
        'message_thread_id': msg.message_thread_id,
        'text': text,
        'reply_markup': markup,
    }

    if msg.ephemeral_message_id is not None:
        send_options.update(
            receiver_user_id=msg.from_user.id,
            reply_parameters=types.ReplyParameters(
                ephemeral_message_id=msg.ephemeral_message_id,
            ),
        )

    try:
        await msg.bot.send_message(**send_options)
    except exceptions.TelegramBadRequest as error:
        if 'reply_to_invalid' not in str(error).lower():
            raise
        send_options.pop('receiver_user_id', None)
        send_options.pop('reply_parameters', None)
        await msg.bot.send_message(**send_options)


async def create_room(
    callback: types.CallbackQuery,
    callback_data: BlackjackCallback,
    bot_storage: BotStorage,
):
    message = _accessible_message(callback)
    if not message:
        await _answer_error(callback, 'localization.system.err_message_inaccessible')
        return

    intended_user_id = _create_button_owner_id(callback_data, message)
    if intended_user_id != callback.from_user.id:
        await _answer_error(callback, 'localization.system.err_not_your_button')
        return

    rooms = bot_storage.scoped('blackjack_rooms')
    player = _make_player(callback.from_user)

    while True:
        room_id = secrets.token_hex(6)
        room: Room = {
            'id': room_id,
            'chat_id': message.chat.id,
            'message_thread_id': message.message_thread_id,
            'message_id': None,
            'players': {str(player['id']): player},
            'owner_id': str(player['id']),
            'status': 'creating',
            'current_player': None,
        }

        try:
            await rooms.mutate(
                room_id,
                lambda current: _reserve_room(current, room),
                default=None,
            )
        except BlackjackActionError:
            continue
        break

    try:
        lobby_message = await callback.bot.send_message(
            chat_id=message.chat.id,
            message_thread_id=room['message_thread_id'],
            text=_waiting_room_text(room),
            reply_markup=_waiting_room_markup(room),
        )

        def activate_room(current: Room | None) -> Room:
            if not current:
                raise BlackjackActionError('localization.rooms.err_not_exists')
            current['message_id'] = lobby_message.message_id
            current['status'] = 'waiting'
            return current

        room = await rooms.mutate(room_id, activate_room, default=None)
    except BaseException:
        await rooms.delete(room_id)
        raise

    await callback.answer()
    await _delete_prompt(message)


async def join_room(
    callback: types.CallbackQuery,
    callback_data: BlackjackCallback,
    bot_storage: BotStorage,
):
    message = _accessible_message(callback)
    if not message:
        await _answer_error(callback, 'localization.system.err_message_inaccessible')
        return

    rooms = bot_storage.scoped('blackjack_rooms')
    player = _make_player(callback.from_user)

    def join(current: Room | None) -> Room:
        room = _waiting_room_from_message(current, message)
        player_id = str(player['id'])
        if player_id in room['players']:
            raise BlackjackActionError('localization.rooms.err_already_joined')
        if len(room['players']) >= config.get('games.blackjack.max_players'):
            raise BlackjackActionError('localization.rooms.err_too_many_players')
        room['players'][player_id] = player
        return room

    try:
        room = await rooms.mutate(callback_data.room_id, join, default=None)
    except BlackjackActionError as error:
        await _answer_error(callback, error.localization_key)
        return

    await callback.answer(
        config.get('localization.rooms.successful_joined').format(
            room=callback_data.room_id,
        )
    )
    await _refresh_waiting_room(message, rooms, callback_data.room_id, room)


async def exit_room(
    callback: types.CallbackQuery,
    callback_data: BlackjackCallback,
    bot_storage: BotStorage,
):
    message = _accessible_message(callback)
    if not message:
        await _answer_error(callback, 'localization.system.err_message_inaccessible')
        return

    rooms = bot_storage.scoped('blackjack_rooms')
    player_id = str(callback.from_user.id)

    def leave(current: Room | None) -> Room:
        room = _waiting_room_from_message(current, message)
        if player_id not in room['players']:
            raise BlackjackActionError('localization.rooms.err_not_joined')
        room['players'].pop(player_id)
        if not room['players']:
            room['status'] = 'closed'
        elif room['owner_id'] == player_id:
            room['owner_id'] = next(iter(room['players']))
        return room

    try:
        room = await rooms.mutate(callback_data.room_id, leave, default=None)
    except BlackjackActionError as error:
        await _answer_error(callback, error.localization_key)
        return

    await callback.answer(
        config.get('localization.rooms.successful_exited').format(
            room=callback_data.room_id,
        )
    )

    if room['status'] == 'closed':
        try:
            await message.edit_text(
                config.get('localization.rooms.closed_due_to_no_players').format(
                    room=callback_data.room_id,
                ),
                reply_markup=None,
            )
        finally:
            await rooms.delete(callback_data.room_id)
        return

    await _refresh_waiting_room(message, rooms, callback_data.room_id, room)


async def start_room(
    callback: types.CallbackQuery,
    callback_data: BlackjackCallback,
    bot_storage: BotStorage,
    storage: PersistentStorage,
):
    message = _accessible_message(callback)
    if not message:
        await _answer_error(callback, 'localization.system.err_message_inaccessible')
        return

    rooms = bot_storage.scoped('blackjack_rooms')
    starter_id = str(callback.from_user.id)

    def start(current: Room | None) -> Room:
        room = _waiting_room_from_message(current, message)
        if not room['players'] or room['owner_id'] != starter_id:
            raise BlackjackActionError('localization.rooms.err_cant_start')
        if len(room['players']) < config.get('games.blackjack.min_players'):
            raise BlackjackActionError('localization.rooms.err_not_enough_players')
        _start_game(room)
        return room

    try:
        room = await rooms.mutate(callback_data.room_id, start, default=None)
    except BlackjackActionError as error:
        await _answer_error(callback, error.localization_key)
        return

    if room['status'] == 'finished':
        await _record_blackjack_statistics(storage, room)

    await message.edit_text(
        rich_message=make_table_layout(room),
        reply_markup=(
            table_room_keyboard(callback_data.room_id)
            if room['status'] == 'active'
            else None
        ),
    )
    await callback.answer()

    if room['status'] == 'finished':
        await rooms.delete(callback_data.room_id)


async def show_controls(
    callback: types.CallbackQuery,
    callback_data: BlackjackCallback,
    bot_storage: BotStorage,
):
    message = _accessible_message(callback)
    if not message:
        await _answer_error(callback, 'localization.system.err_message_inaccessible')
        return

    rooms = bot_storage.scoped('blackjack_rooms')
    room = await rooms.get(callback_data.room_id)

    try:
        room = _active_room_from_table(room, message)
        player = _room_player(room, callback.from_user.id)
    except BlackjackActionError as error:
        await _answer_error(callback, error.localization_key)
        return

    if room['current_player'] != str(player['id']):
        current_player = room['players'].get(room['current_player'])
        current_name = current_player['name'] if current_player else ''
        await callback.answer(
            config.get('localization.rooms.err_not_your_turn').format(
                player=current_name,
            ),
            show_alert=True,
        )
        return

    try:
        control_message = await callback.bot.send_message(
            chat_id=room['chat_id'],
            message_thread_id=room.get('message_thread_id'),
            text=_controls_text(player),
            receiver_user_id=callback.from_user.id,
            callback_query_id=callback.id,
            reply_markup=active_room_keyboard(
                room_id=callback_data.room_id,
                can_hit=True,
                can_stand=True,
            ),
        )
    except exceptions.TelegramBadRequest:
        await callback.answer(
            config.get('localization.blackjack.room.active.control.unavailable'),
            show_alert=True,
        )
        return

    if control_message.ephemeral_message_id is None:
        await control_message.delete()
        await callback.answer(
            config.get('localization.blackjack.room.active.control.unavailable'),
            show_alert=True,
        )
        return

    await callback.answer()


async def action_hit(
    callback: types.CallbackQuery,
    callback_data: BlackjackCallback,
    bot_storage: BotStorage,
    storage: PersistentStorage,
):
    await _perform_player_action(
        callback,
        callback_data,
        bot_storage,
        storage,
        action='hit',
    )


async def action_stand(
    callback: types.CallbackQuery,
    callback_data: BlackjackCallback,
    bot_storage: BotStorage,
    storage: PersistentStorage,
):
    await _perform_player_action(
        callback,
        callback_data,
        bot_storage,
        storage,
        action='stand',
    )


async def _perform_player_action(
    callback: types.CallbackQuery,
    callback_data: BlackjackCallback,
    bot_storage: BotStorage,
    storage: PersistentStorage,
    *,
    action: str,
):
    message = _accessible_message(callback)
    if not message:
        await _answer_error(callback, 'localization.system.err_message_inaccessible')
        return

    rooms = bot_storage.scoped('blackjack_rooms')
    user_id = str(callback.from_user.id)

    def perform(current: Room | None) -> Room:
        room = _active_room(current)
        player = _room_player(room, callback.from_user.id)
        if room['current_player'] != user_id or player['state'] != 'playing':
            raise BlackjackActionError('localization.rooms.err_not_your_turn')
        _apply_player_action(room, user_id, action)
        return room

    try:
        room = await rooms.mutate(callback_data.room_id, perform, default=None)
    except BlackjackActionError as error:
        await _answer_error(callback, error.localization_key)
        return

    if room['status'] == 'finished':
        await _record_blackjack_statistics(storage, room)

    await callback.answer()

    await callback.bot.edit_message_text(
        chat_id=room['chat_id'],
        message_id=room['message_id'],
        rich_message=make_table_layout(room),
        reply_markup=(
            table_room_keyboard(callback_data.room_id)
            if room['status'] == 'active'
            else None
        ),
    )

    await _update_personal_controls(message, room, callback.from_user.id)

    if room['status'] == 'finished':
        await rooms.delete(callback_data.room_id)


def _reserve_room(current: Room | None, room: Room) -> Room:
    if current is not None:
        raise BlackjackActionError('localization.rooms.err_room_id_collision')
    return room


def _waiting_room_from_message(
    room: Room | None,
    message: types.Message,
) -> Room:
    if not room:
        raise BlackjackActionError('localization.rooms.err_not_exists')
    if room.get('status') != 'waiting':
        raise BlackjackActionError('localization.rooms.err_room_not_waiting')
    if room.get('chat_id') != message.chat.id or room.get('message_id') != message.message_id:
        raise BlackjackActionError('localization.system.err_message_inaccessible')
    return room


def _active_room(room: Room | None) -> Room:
    if not room:
        raise BlackjackActionError('localization.rooms.err_not_exists')
    if room.get('status') != 'active':
        raise BlackjackActionError('localization.rooms.err_game_not_active')
    return room


def _active_room_from_table(room: Room | None, message: types.Message) -> Room:
    room = _active_room(room)
    if room.get('chat_id') != message.chat.id or room.get('message_id') != message.message_id:
        raise BlackjackActionError('localization.system.err_message_inaccessible')
    return room


def _room_player(room: Room, user_id: int) -> Player:
    player = room['players'].get(str(user_id))
    if not player:
        raise BlackjackActionError('localization.rooms.err_not_joined')
    return player


def _make_player(user: types.User) -> Player:
    return {
        'id': user.id,
        'name': user.full_name,
        'username': user.username,
        'hand': [],
        'state': 'waiting',
        'result': None,
    }


def _start_game(room: Room) -> None:
    room['status'] = 'active'
    room['deck'] = get_deck(size=52, shuffle=True)
    room['dealer'] = {
        'id': -1,
        'name': config.get('localization.blackjack.dealer_name'),
        'hand': [],
        'show_full_hand': False,
    }
    room['turn_order'] = list(room['players'])

    for player in room['players'].values():
        player['hand'] = []
        player['state'] = 'playing'
        player['result'] = None

    participants = [*room['players'].values(), room['dealer']]
    for participant in participants * 2:
        participant['hand'].append(_draw_card(room))

    for player in room['players'].values():
        if get_hand_sum(player['hand']) == 21:
            player['state'] = 'blackjack'

    dealer_has_blackjack = get_hand_sum(room['dealer']['hand']) == 21
    room['current_player'] = (
        None if dealer_has_blackjack else _first_playing_player(room)
    )
    if room['current_player'] is None:
        _finish_game(room)


def _apply_player_action(room: Room, player_id: str, action: str) -> None:
    player = room['players'][player_id]
    if action == 'hit':
        player['hand'].append(_draw_card(room))
        score = get_hand_sum(player['hand'])
        if score > 21:
            player['state'] = 'busted'
        elif score == 21:
            player['state'] = 'stood'
    elif action == 'stand':
        player['state'] = 'stood'
    else:
        raise ValueError(f'unsupported blackjack action: {action}')

    if player['state'] != 'playing':
        room['current_player'] = _next_playing_player(room, player_id)
        if room['current_player'] is None:
            _finish_game(room)


def _draw_card(room: Room) -> str:
    if not room.get('deck'):
        raise BlackjackActionError('localization.rooms.err_deck_empty')
    return room['deck'].pop()


def _first_playing_player(room: Room) -> str | None:
    return next(
        (
            player_id
            for player_id in room['turn_order']
            if room['players'][player_id]['state'] == 'playing'
        ),
        None,
    )


def _next_playing_player(room: Room, current_player_id: str) -> str | None:
    current_index = room['turn_order'].index(current_player_id)
    return next(
        (
            player_id
            for player_id in room['turn_order'][current_index + 1:]
            if room['players'][player_id]['state'] == 'playing'
        ),
        None,
    )


def _finish_game(room: Room) -> None:
    make_dealer_move(room)
    calc_game_results(room)
    room['status'] = 'finished'
    room['current_player'] = None


def make_dealer_move(room: Room) -> None:
    dealer = room['dealer']
    dealer['show_full_hand'] = True
    while get_hand_sum(dealer['hand']) < 17:
        dealer['hand'].append(_draw_card(room))


def calc_game_results(room: Room) -> None:
    dealer_hand = room['dealer']['hand']
    dealer_score = get_hand_sum(dealer_hand)
    dealer_blackjack = len(dealer_hand) == 2 and dealer_score == 21

    for player in room['players'].values():
        hand = player['hand']
        score = get_hand_sum(hand)
        player_blackjack = len(hand) == 2 and score == 21

        if score > 21:
            result = 'lose'
        elif player_blackjack and not dealer_blackjack:
            result = 'blackjack'
        elif dealer_score > 21:
            result = 'win'
        elif dealer_blackjack and not player_blackjack:
            result = 'lose'
        elif score > dealer_score:
            result = 'win'
        elif score < dealer_score:
            result = 'lose'
        else:
            result = 'push'

        player['result'] = result


def _add_blackjack_result(
    current: Any,
    *,
    room_id: str,
    result: str,
) -> dict[str, Any]:
    result_fields = {
        'win': 'wins',
        'lose': 'losses',
        'push': 'pushes',
        'blackjack': 'wins',
    }
    if result not in result_fields:
        raise ValueError(f'unsupported blackjack result: {result}')

    stats = dict(current) if isinstance(current, dict) else {}
    recorded_game_ids = stats.get('recorded_game_ids')
    if not isinstance(recorded_game_ids, list):
        recorded_game_ids = []
    recorded_game_ids = [
        str(game_id)
        for game_id in recorded_game_ids
        if isinstance(game_id, (str, int))
    ]

    room_id = str(room_id)
    if room_id in recorded_game_ids:
        return stats

    for field in ('played', 'wins', 'losses', 'pushes', 'blackjacks'):
        value = stats.get(field, 0)
        stats[field] = (
            max(0, int(value))
            if isinstance(value, (int, float)) and not isinstance(value, bool)
            else 0
        )

    stats['played'] += 1
    stats[result_fields[result]] += 1
    if result == 'blackjack':
        stats['blackjacks'] += 1

    stats['recorded_game_ids'] = [*recorded_game_ids, room_id][-100:]
    return stats


async def _record_blackjack_statistics(
    storage: PersistentStorage,
    room: Room,
) -> None:
    room_id = str(room['id'])

    async def record(player: Player) -> None:
        result = player.get('result')
        if not isinstance(result, str):
            raise ValueError('blackjack player result is missing')
        await storage.for_user(player['id']).mutate(
            'blackjack_stats',
            lambda current: _add_blackjack_result(
                current,
                room_id=room_id,
                result=result,
            ),
            default={},
        )

    await asyncio.gather(*(record(player) for player in room['players'].values()))


def make_table_layout(room: Room) -> types.InputRichMessage:
    dealer = room['dealer']
    if dealer['show_full_hand']:
        dealer_hand = dealer['hand']
        dealer_result = str(get_hand_sum(dealer_hand))
    else:
        dealer_hand = [dealer['hand'][0], '##']
        dealer_result = ''

    rows = [
        _table_row(dealer['name'], dealer_hand, dealer_result),
        *(
            _table_row(
                player['name'],
                player['hand'],
                _player_result_text(player),
            )
            for player in room['players'].values()
        ),
    ]

    if room['status'] == 'active':
        current = room['players'][room['current_player']]
        status = config.get('localization.blackjack.playtime.turn').format(
            player=html.escape(current['name']),
        )
    else:
        status = config.get('localization.blackjack.playtime.finished')

    return types.InputRichMessage(
        html=config.get('localization.blackjack.playtime.table_layout.body').format(
            room=html.escape(str(room['id'])),
            status=status,
            rows=''.join(rows),
        )
    )


def _table_row(player_name: str, hand: Sequence[str], result: str) -> str:
    return config.get('localization.blackjack.playtime.table_layout.row').format(
        player=html.escape(player_name),
        cards=html.escape(', '.join(hand)),
        result=html.escape(result),
    )


def _player_result_text(player: Player) -> str:
    score = get_hand_sum(player['hand'])
    if not player.get('result'):
        state_key = f'localization.blackjack.playtime.state.{player['state']}'
        state_text = config.get(state_key, '')
        return f'{score} {state_text}'.strip()

    result_key = f'localization.blackjack.playtime.result.{player['result']}'
    return f'{score} {config.get(result_key)}'


def get_hand_sum(hand: Sequence[str]) -> int:
    total = 0
    aces = 0

    for card in hand:
        if len(card) < 2:
            continue
        value = card[:-1]
        if value.isdigit():
            total += int(value)
        elif value == 'A':
            total += 11
            aces += 1
        else:
            total += 10

    while total > 21 and aces:
        total -= 10
        aces -= 1
    return total


def _waiting_room_text(room: Room) -> str:
    player_names = ', '.join(
        html.escape(player['name'])
        for player in room['players'].values()
    )
    return config.get('localization.blackjack.room.waiting').format(
        room=html.escape(str(room['id'])),
        players=player_names,
    )


def _waiting_room_markup(room: Room) -> types.InlineKeyboardMarkup:
    players_count = len(room['players'])
    return waiting_room_keyboard(
        room_id=room['id'],
        joined_players=players_count,
        max_players=config.get('games.blackjack.max_players'),
        can_start=players_count >= config.get('games.blackjack.min_players'),
    )


async def _refresh_waiting_room(
    message: types.Message,
    rooms: BotStorage,
    room_id: str,
    fallback_room: Room,
) -> None:
    room = await rooms.get(room_id) or fallback_room
    if room.get('status') != 'waiting':
        return
    await message.edit_text(
        _waiting_room_text(room),
        reply_markup=_waiting_room_markup(room),
    )


def _controls_text(player: Player) -> str:
    return config.get('localization.blackjack.room.active.control.message').format(
        score=get_hand_sum(player['hand']),
    )


async def _update_personal_controls(
    message: types.Message,
    room: Room,
    player_id: int,
) -> None:
    player = room['players'][str(player_id)]
    if room['status'] == 'finished':
        text = config.get('localization.blackjack.room.active.control.finished').format(
            result=_player_result_text(player),
        )
        markup = None
    elif room['current_player'] == str(player_id):
        text = _controls_text(player)
        markup = active_room_keyboard(
            room_id=room['id'],
            can_hit=True,
            can_stand=True,
        )
    else:
        current = room['players'][room['current_player']]
        text = config.get(
            'localization.blackjack.room.active.control.waiting_other_players'
        ).format(player=current['name'])
        markup = None

    try:
        if message.ephemeral_message_id is not None:
            await message.edit_ephemeral_text(text=text, reply_markup=markup)
        else:
            await message.edit_text(text=text, reply_markup=markup)
    except exceptions.TelegramBadRequest as error:
        if 'message is not modified' not in str(error).lower():
            raise


def _accessible_message(callback: types.CallbackQuery) -> types.Message | None:
    if not callback.message or isinstance(callback.message, types.InaccessibleMessage):
        return None
    return callback.message


def _intended_receiver_id(message: types.Message) -> int | None:
    if message.receiver_user:
        return message.receiver_user.id
    if message.reply_to_message and message.reply_to_message.from_user:
        return message.reply_to_message.from_user.id
    return None


def _create_button_owner_id(
    callback_data: BlackjackCallback,
    message: types.Message,
) -> int | None:
    try:
        return int(callback_data.room_id)
    except (TypeError, ValueError):
        return _intended_receiver_id(message)


async def _delete_prompt(message: types.Message) -> None:
    try:
        if message.ephemeral_message_id is not None:
            await message.delete_ephemeral()
        else:
            await message.delete()
    except (AssertionError, exceptions.TelegramBadRequest):
        # The public lobby is already created; an expired prompt is harmless.
        return


async def _answer_error(callback: types.CallbackQuery, localization_key: str) -> None:
    await callback.answer(config.get(localization_key), show_alert=True)
