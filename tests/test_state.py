import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

from handlers import blackjack, state
from storage import PersistentStorage


class StatisticsTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        database_path = Path(self.temporary_directory.name) / 'test.db'
        self.storage = PersistentStorage(f'sqlite+aiosqlite:///{database_path}')
        await self.storage.initialize()

    async def asyncTearDown(self) -> None:
        await self.storage.close()
        self.temporary_directory.cleanup()

    async def test_stats_include_slots_blackjack_and_totals(self) -> None:
        user_storage = self.storage.for_user(1)
        await user_storage.set_many(
            {
                'total_slot_play_count': 10,
                'total_slot_wins': 3,
                'total_slot_earned': 500,
                'total_slot_lost': 200,
                'blackjack_stats': {
                    'played': 5,
                    'wins': 3,
                    'losses': 1,
                    'pushes': 1,
                    'blackjacks': 1,
                },
            }
        )
        message = SimpleNamespace(reply=AsyncMock())

        await state.stats(message, user_storage)

        text = message.reply.await_args.args[0]
        self.assertIn('<b>📊 Общая статистика</b>', text)
        self.assertIn('Игр: 15', text)
        self.assertIn('Побед: 6', text)
        self.assertIn('Поражений: 8', text)
        self.assertIn('Винрейт: 40.0%', text)
        self.assertIn('<b>🎰 Слоты</b>', text)
        self.assertIn('Выиграно: 500', text)
        self.assertIn('Проиграно: 200', text)
        self.assertIn('<b>🃏 Блэкджек</b>', text)
        self.assertIn('Блэкджеков с раздачи: 1', text)

    async def test_empty_stats_do_not_divide_by_zero(self) -> None:
        message = SimpleNamespace(reply=AsyncMock())

        await state.stats(message, self.storage.for_user(1))

        text = message.reply.await_args.args[0]
        self.assertEqual(text.count('Винрейт: 0.0%'), 3)

    async def test_blackjack_results_are_recorded_once_per_room(self) -> None:
        room = {
            'id': 'room-1',
            'players': {
                '1': {'id': 1, 'result': 'blackjack'},
                '2': {'id': 2, 'result': 'lose'},
            },
        }

        await blackjack._record_blackjack_statistics(self.storage, room)
        await blackjack._record_blackjack_statistics(self.storage, room)

        winner = await self.storage.for_user(1).get('blackjack_stats')
        loser = await self.storage.for_user(2).get('blackjack_stats')
        self.assertEqual(winner['played'], 1)
        self.assertEqual(winner['wins'], 1)
        self.assertEqual(winner['blackjacks'], 1)
        self.assertEqual(loser['played'], 1)
        self.assertEqual(loser['losses'], 1)


if __name__ == '__main__':
    unittest.main()
