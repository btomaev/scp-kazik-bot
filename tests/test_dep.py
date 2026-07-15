import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from handlers import dep
from storage import PersistentStorage


class DepositHandlerTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        database_path = Path(self.temporary_directory.name) / "test.db"
        self.storage = PersistentStorage(
            f"sqlite+aiosqlite:///{database_path}",
        )
        await self.storage.initialize()
        self.user_storage = self.storage.for_user(1)

    async def asyncTearDown(self) -> None:
        await self.storage.close()
        self.temporary_directory.cleanup()

    async def test_slot_accepts_bet_from_command(self) -> None:
        await self.user_storage.set("balance", 1_000)
        message = SimpleNamespace(
            text="/slot 100",
            reply=AsyncMock(),
            answer=AsyncMock(),
            reply_dice=AsyncMock(
                return_value=SimpleNamespace(
                    dice=SimpleNamespace(value=2),
                ),
            ),
        )

        with patch("handlers.dep.asyncio.sleep", new=AsyncMock()):
            await dep.slot(message, self.user_storage)

        self.assertEqual(await self.user_storage.get("balance"), 900)
        self.assertEqual(await self.user_storage.get("deposit"), 0)
        self.assertEqual(await self.user_storage.get("total_deps_count"), 1)
        self.assertEqual(await self.user_storage.get("total_slot_play_count"), 1)
        self.assertEqual(await self.user_storage.get("total_lost"), 100)
        message.reply_dice.assert_awaited_once_with(emoji="🎰")

    async def test_dep_uses_shared_bet_logic(self) -> None:
        await self.user_storage.set("balance", 1_000)
        message = SimpleNamespace(
            text="/dep 100",
            reply=AsyncMock(),
        )

        await dep.dep(message, self.user_storage)

        self.assertEqual(await self.user_storage.get("balance"), 900)
        self.assertEqual(await self.user_storage.get("deposit"), 100)
        self.assertEqual(await self.user_storage.get("total_deps_count"), 1)

    async def test_slot_does_not_start_when_bet_exceeds_balance(self) -> None:
        await self.user_storage.set("balance", 50)
        message = SimpleNamespace(
            text="/slot 100",
            reply=AsyncMock(),
            answer=AsyncMock(),
            reply_dice=AsyncMock(),
        )

        await dep.slot(message, self.user_storage)

        self.assertEqual(await self.user_storage.get("balance"), 50)
        self.assertEqual(await self.user_storage.get("deposit", 0), 0)
        message.reply_dice.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
