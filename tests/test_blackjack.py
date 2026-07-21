import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import config
from aiogram import exceptions
from aiogram.methods import SendMessage
from handlers import blackjack
from util.cards import get_deck


def make_player(
    player_id: int,
    hand: list[str],
    *,
    name: str | None = None,
    state: str = 'playing',
) -> dict:
    return {
        'id': player_id,
        'name': name or f'Player {player_id}',
        'username': None,
        'hand': hand,
        'state': state,
        'result': None,
    }


class DeckTests(unittest.TestCase):
    def test_deck_sizes_and_lowest_ranks(self) -> None:
        expected = {
            24: '9',
            32: '7',
            36: '6',
            52: '2',
            54: '2',
        }

        for size, first_rank in expected.items():
            with self.subTest(size=size):
                deck = get_deck(size)
                self.assertEqual(len(deck), size)
                self.assertTrue(deck[0].startswith(first_rank))

    def test_unsupported_deck_size_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            get_deck(20)  # type: ignore[arg-type]


class BlackjackRulesTests(unittest.TestCase):
    def test_hand_sum_handles_multiple_aces(self) -> None:
        cases = {
            ('A♠', 'A♥', '9♦'): 21,
            ('A♠', 'A♥', 'K♦'): 12,
            ('A♠', 'A♥', 'A♦', '9♣'): 12,
            ('10♠', 'K♥', '2♦'): 22,
        }

        for hand, expected in cases.items():
            with self.subTest(hand=hand):
                self.assertEqual(blackjack.get_hand_sum(hand), expected)

    def test_dealer_hits_on_sixteen_and_stands_on_seventeen(self) -> None:
        room = {
            'deck': ['2♣'],
            'dealer': {
                'hand': ['10♠', '6♥'],
                'show_full_hand': False,
            },
        }

        blackjack.make_dealer_move(room)

        self.assertEqual(room['dealer']['hand'], ['10♠', '6♥', '2♣'])
        self.assertTrue(room['dealer']['show_full_hand'])

    def test_results_cover_blackjack_win_loss_and_push(self) -> None:
        room = {
            'dealer': {'hand': ['10♠', '7♥']},
            'players': {
                '1': make_player(1, ['A♠', 'K♥'], state='blackjack'),
                '2': make_player(2, ['10♦', '9♣'], state='stood'),
                '3': make_player(3, ['10♦', '6♣'], state='stood'),
                '4': make_player(4, ['10♥', '7♠'], state='stood'),
                '5': make_player(5, ['10♥', 'K♠', '2♦'], state='busted'),
            },
        }

        blackjack.calc_game_results(room)

        self.assertEqual(room['players']['1']['result'], 'blackjack')
        self.assertEqual(room['players']['2']['result'], 'win')
        self.assertEqual(room['players']['3']['result'], 'lose')
        self.assertEqual(room['players']['4']['result'], 'push')
        self.assertEqual(room['players']['5']['result'], 'lose')

    def test_turn_advances_and_last_bust_finishes_game(self) -> None:
        room = {
            'status': 'active',
            'deck': ['10♣'],
            'players': {
                '1': make_player(1, ['10♠', '8♥']),
                '2': make_player(2, ['10♦', '5♣']),
            },
            'dealer': {
                'id': -1,
                'name': 'Dealer',
                'hand': ['10♥', '7♠'],
                'show_full_hand': False,
            },
            'turn_order': ['1', '2'],
            'current_player': '1',
        }

        blackjack._apply_player_action(room, '1', 'stand')
        self.assertEqual(room['current_player'], '2')
        self.assertEqual(room['status'], 'active')

        blackjack._apply_player_action(room, '2', 'hit')
        self.assertEqual(room['status'], 'finished')
        self.assertIsNone(room['current_player'])
        self.assertEqual(room['players']['2']['state'], 'busted')
        self.assertTrue(room['dealer']['show_full_hand'])

    def test_dealer_blackjack_finishes_game_immediately(self) -> None:
        room = {
            'id': 'room',
            'players': {'1': make_player(1, [])},
            'status': 'waiting',
        }
        deck = ['K♥', '9♣', 'A♠', '8♦']

        with patch('handlers.blackjack.get_deck', return_value=deck):
            blackjack._start_game(room)

        self.assertEqual(room['status'], 'finished')
        self.assertIsNone(room['current_player'])
        self.assertEqual(room['players']['1']['result'], 'lose')
        self.assertTrue(room['dealer']['show_full_hand'])

    def test_table_escapes_player_names(self) -> None:
        room = {
            'id': 'room',
            'status': 'active',
            'current_player': '1',
            'players': {
                '1': make_player(1, ['10♠', '7♥'], name='<b>Alice</b>'),
            },
            'dealer': {
                'name': 'Dealer',
                'hand': ['A♠', 'K♥'],
                'show_full_hand': False,
            },
        }

        layout = blackjack.make_table_layout(room)

        self.assertIn('&lt;b&gt;Alice&lt;/b&gt;', layout.html)
        self.assertNotIn('<b>Alice</b>', layout.html)

    def test_required_localization_keys_exist(self) -> None:
        self.assertIsNotNone(config.get('localization.rooms.err_not_enough_players'))
        self.assertIsNotNone(config.get('localization.blackjack.playtime.controls_btn'))


class EphemeralControlTests(unittest.IsolatedAsyncioTestCase):
    async def test_room_is_created_in_command_topic(self) -> None:
        stored_rooms = {}

        async def mutate(room_id, transform, *, default=None):
            room = transform(stored_rooms.get(room_id, default))
            stored_rooms[room_id] = room
            return room

        rooms = SimpleNamespace(
            mutate=AsyncMock(side_effect=mutate),
            delete=AsyncMock(),
        )
        bot_storage = SimpleNamespace(scoped=lambda _: rooms)
        message = SimpleNamespace(
            chat=SimpleNamespace(id=-100),
            message_thread_id=77,
            ephemeral_message_id=None,
            delete=AsyncMock(),
        )
        lobby_message = SimpleNamespace(message_id=50)
        bot = SimpleNamespace(send_message=AsyncMock(return_value=lobby_message))
        callback = SimpleNamespace(
            message=message,
            from_user=SimpleNamespace(
                id=1,
                full_name='Player',
                username=None,
            ),
            bot=bot,
            answer=AsyncMock(),
        )
        callback_data = SimpleNamespace(room_id='1')

        with patch('handlers.blackjack.secrets.token_hex', return_value='room'):
            await blackjack.create_room(callback, callback_data, bot_storage)

        kwargs = bot.send_message.await_args.kwargs
        self.assertEqual(kwargs['chat_id'], -100)
        self.assertEqual(kwargs['message_thread_id'], 77)
        self.assertEqual(stored_rooms['room']['message_thread_id'], 77)

    async def test_command_uses_explicit_ephemeral_reply_target(self) -> None:
        bot = SimpleNamespace(send_message=AsyncMock())
        message = SimpleNamespace(
            from_user=SimpleNamespace(id=42),
            ephemeral_message_id=7,
            chat=SimpleNamespace(id=-100),
            message_thread_id=77,
            bot=bot,
        )

        await blackjack.blackjack(message)

        kwargs = bot.send_message.await_args.kwargs
        self.assertEqual(kwargs['chat_id'], -100)
        self.assertEqual(kwargs['message_thread_id'], 77)
        self.assertEqual(kwargs['receiver_user_id'], 42)
        self.assertEqual(kwargs['reply_parameters'].ephemeral_message_id, 7)
        callback_data = kwargs['reply_markup'].inline_keyboard[0][0].callback_data
        self.assertEqual(callback_data, 'blackjack:create:42')

    async def test_command_falls_back_when_ephemeral_reply_expired(self) -> None:
        error = exceptions.TelegramBadRequest(
            method=SendMessage(chat_id=-100, text='test'),
            message='Bad Request: REPLY_TO_INVALID',
        )
        bot = SimpleNamespace(
            send_message=AsyncMock(side_effect=[error, SimpleNamespace()]),
        )
        message = SimpleNamespace(
            from_user=SimpleNamespace(id=42),
            ephemeral_message_id=7,
            chat=SimpleNamespace(id=-100),
            message_thread_id=77,
            bot=bot,
        )

        await blackjack.blackjack(message)

        self.assertEqual(bot.send_message.await_count, 2)
        fallback_kwargs = bot.send_message.await_args_list[1].kwargs
        self.assertEqual(fallback_kwargs['message_thread_id'], 77)
        self.assertNotIn('receiver_user_id', fallback_kwargs)
        self.assertNotIn('reply_parameters', fallback_kwargs)

    async def test_show_controls_targets_callback_sender(self) -> None:
        room = {
            'id': 'room',
            'chat_id': -100,
            'message_thread_id': 77,
            'message_id': 50,
            'status': 'active',
            'current_player': '1',
            'players': {'1': make_player(1, ['10♠', '7♥'])},
        }
        message = SimpleNamespace(
            chat=SimpleNamespace(id=-100),
            message_id=50,
        )
        control_message = SimpleNamespace(ephemeral_message_id=12)
        bot = SimpleNamespace(
            send_message=AsyncMock(return_value=control_message),
        )
        callback = SimpleNamespace(
            id='callback-id',
            message=message,
            from_user=SimpleNamespace(id=1),
            answer=AsyncMock(),
            bot=bot,
        )
        rooms = SimpleNamespace(get=AsyncMock(return_value=room))
        bot_storage = SimpleNamespace(scoped=lambda _: rooms)
        callback_data = SimpleNamespace(room_id='room')

        await blackjack.show_controls(callback, callback_data, bot_storage)

        bot.send_message.assert_awaited_once()
        kwargs = bot.send_message.await_args.kwargs
        self.assertEqual(kwargs['chat_id'], -100)
        self.assertEqual(kwargs['message_thread_id'], 77)
        self.assertEqual(kwargs['receiver_user_id'], 1)
        self.assertEqual(kwargs['callback_query_id'], 'callback-id')
        callback.answer.assert_awaited_once_with()

    async def test_personal_controls_use_ephemeral_edit_method(self) -> None:
        room = {
            'id': 'room',
            'status': 'active',
            'current_player': '1',
            'players': {'1': make_player(1, ['10♠', '7♥'])},
        }
        message = SimpleNamespace(
            ephemeral_message_id=12,
            edit_ephemeral_text=AsyncMock(),
            edit_text=AsyncMock(),
        )

        await blackjack._update_personal_controls(message, room, 1)

        message.edit_ephemeral_text.assert_awaited_once()
        message.edit_text.assert_not_awaited()


if __name__ == '__main__':
    unittest.main()
