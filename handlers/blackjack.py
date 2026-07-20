import random

from aiogram import types

import config
from keyboards.blackjack import BlackjackCallback, waiting_room_keyboard, make_room_keyboard
from storage import BotStorage
from util.cards import get_deck


async def blackjack(msg: types.Message, storage: BotStorage):
    if not msg.from_user:
        return
    await msg.reply(
        config.get('localization.blackjack.room.make'),
        reply_markup=make_room_keyboard(),
    )


async def create_room(callback: types.CallbackQuery, bot_storage: BotStorage):
    if not callback.message or \
       isinstance(callback.message, types.InaccessibleMessage) or \
       not callback.message.reply_to_message:
        await callback.answer(config.get('localization.system.err_message_inaccessible'))
        return
    
    player = callback.from_user
    
    if player != callback.message.reply_to_message.from_user:
        await callback.answer(config.get('localization.system.err_not_your_button'))
        return
    
    await callback.answer()

    rooms = bot_storage.scoped('blackjack_rooms')
    room_id = str(random.randint(0, 100000))
    players = {
        player.id: {
            'id': player.id,
            'name': player.full_name,
            'username': player.username,
            'hand': [],
        }
    }

    await rooms.set(room_id, {
        'players': players,
        'status': 'waiting',
    })

    await callback.message.edit_text(
        text=config.get(
            'localization.blackjack.room.waiting'
            ).format(
                room=room_id,
                players=', '.join([p['username'] for p in players.values()])
            ),
        reply_markup=waiting_room_keyboard(
            room_id=room_id,
            joined_players=1,
            max_players=config.get('games.blackjack.max_players'),
            can_start=1 >= config.get('games.blackjack.min_players')
        )
    )


async def join_room(callback: types.CallbackQuery, callback_data: BlackjackCallback, bot_storage: BotStorage):
    if not callback.message or isinstance(callback.message, types.InaccessibleMessage):
        await callback.answer(config.get('localization.system.err_message_inaccessible'))
        return
    
    rooms = bot_storage.scoped('blackjack_rooms')
    room_id = callback_data.room_id
    room = await rooms.get(room_id)
    player = callback.from_user

    if not room:
        await callback.answer(config.get('localization.rooms.err_not_exists'))
        return
    
    if str(player.id) in room['players']:
        await callback.answer(config.get('localization.rooms.err_already_joined'))
        return
    
    players_count = len(room['players'])
    if players_count >= config.get('games.blackjack.max_players'):
        await callback.message.answer(config.get('localization.rooms.err_too_many_players'))
        return
    
    room['players'].update(
        {
            player.id: {
                'id': player.id,
                'name': player.full_name,
                'username': player.username,
                'hand': [],
            }
        })
    players_count = len(room['players'])

    await rooms.set(room_id, room)
    
    await callback.answer(
        text=config.get(
            'localization.rooms.successful_joined'
        ).format(
            room=room_id
        )
    )
    await callback.message.edit_text(
        text=config.get(
            'localization.blackjack.room.waiting'
            ).format(
                room=room_id,
                players=', '.join([p['username'] for p in room['players'].values()])
            ),
        reply_markup=waiting_room_keyboard(
            room_id=room_id,
            joined_players=players_count,
            max_players=config.get('games.blackjack.max_players'),
            can_start=players_count >= config.get('games.blackjack.min_players')
        )
    )


async def exit_room(callback: types.CallbackQuery, callback_data: BlackjackCallback, bot_storage: BotStorage):
    if not callback.message or isinstance(callback.message, types.InaccessibleMessage):
        await callback.answer(config.get('localization.system.err_message_inaccessible'))
        return
    
    rooms = bot_storage.scoped('blackjack_rooms')
    room_id = callback_data.room_id
    room = await rooms.get(room_id)
    player = callback.from_user

    if not room:
        await callback.answer(config.get('localization.rooms.err_not_exists'))
        return
    
    if str(player.id) not in room['players']:
        await callback.answer(config.get('localization.rooms.err_not_joined'))
        return
    
    room['players'].pop(str(player.id))
    players_count = len(room['players'])

    await rooms.set(room_id, room)
    
    await callback.answer(
        text=config.get(
            'localization.rooms.successful_exited'
        ).format(
            room=room_id,
        )
    )

    if players_count > 0:
        await callback.message.edit_text(
            text=config.get(
                'localization.blackjack.room.waiting'
            ).format(
                room=room_id,
                players=', '.join([p['username'] for p in room['players'].values()])
            ),
            reply_markup=waiting_room_keyboard(
                room_id=room_id,
                joined_players=players_count,
                max_players=config.get('games.blackjack.max_players'),
                can_start=players_count >= config.get('games.blackjack.min_players')
            )
        )
    else:
        await callback.message.edit_text(
            text=config.get(
                'localization.rooms.closed_due_to_no_players'
            ).format(
                room=room_id
            ),
            reply_markup=None
        )

    
async def start_room(callback: types.CallbackQuery, callback_data: BlackjackCallback, bot_storage: BotStorage):
    if not callback.message or \
       isinstance(callback.message, types.InaccessibleMessage) or \
       not callback.message.reply_to_message:
        await callback.answer(config.get('localization.system.err_message_inaccessible'))
        return
    
    rooms = bot_storage.scoped('blackjack_rooms')
    room_id = callback_data.room_id
    room = await rooms.get(room_id)
    player = callback.from_user

    if not room:
        await callback.answer(config.get('localization.rooms.err_not_exists'))
        return
    
    if not room['players'] or list(room['players'])[0] != str(player.id):
        await callback.answer(config.get('localization.rooms.err_cant_start'))
        return
    
    players_count = len(room['players'])

    if players_count < config.get('games.blackjack.min_players'):
        await callback.answer(config.get('localization.rooms.err_not_enough_players'))
        return
    
    room['status'] = 'active'
    room['deck'] = get_deck(size=52, shuffle=True)

    await rooms.set(room_id, room)
    
    room['dealer'] = {
        'name': config.get('localization.blackjack.dealer_name'),
        'hand': []
    }

    players = [*room['players'].values(), room['dealer']]

    for player in players * 2:
        player['hand'].append(room['deck'].pop())

    rich_message = types.InputRichMessage(
        html=config.get(
            'localization.blackjack.playtime.table_layout.body'
        ).format(
            room=room_id,
            rows=
            ''.join([
                config.get(
                    'localization.blackjack.playtime.table_layout.row'
                ).format(
                    player=room['dealer']['name'],
                    cards=', '.join([room['dealer']['hand'][0], '##'])
                )
            ])
            +
            ''.join([
                config.get(
                    'localization.blackjack.playtime.table_layout.row'
                ).format(
                    player=p['name'],
                    cards=', '.join(p['hand'])
                )
                for p in room['players'].values()
            ])
        )
    )

    await callback.message.delete()
    await callback.message.reply_to_message.reply_rich(
        rich_message=rich_message
    )