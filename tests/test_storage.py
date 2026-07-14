import asyncio
import tempfile
import unittest
from pathlib import Path

from storage import PersistentStorage


class PersistentStorageTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        database_path = Path(self.temporary_directory.name) / "test.db"
        self.database_url = f"sqlite+aiosqlite:///{database_path}"
        self.storage = PersistentStorage(self.database_url)
        await self.storage.initialize()

    async def asyncTearDown(self) -> None:
        await self.storage.close()
        self.temporary_directory.cleanup()

    async def test_user_values_are_isolated(self) -> None:
        first_user = self.storage.for_user(1)
        second_user = self.storage.for_user(2)

        await first_user.set("profile", {"name": "Alice"})
        await second_user.set("profile", {"name": "Bob"})

        self.assertEqual(await first_user.get("profile"), {"name": "Alice"})
        self.assertEqual(await second_user.get("profile"), {"name": "Bob"})

    async def test_bot_and_user_values_are_separate(self) -> None:
        user_storage = self.storage.for_user(1)
        await user_storage.set("enabled", False)
        await self.storage.bot.set("enabled", True)

        self.assertFalse(await user_storage.get("enabled"))
        self.assertTrue(await self.storage.bot.get("enabled"))

    async def test_missing_and_stored_null_are_distinguishable(self) -> None:
        await self.storage.bot.set("nullable", None)

        self.assertIsNone(await self.storage.bot.get("nullable", "fallback"))
        self.assertEqual(await self.storage.bot.get("missing", "fallback"), "fallback")

    async def test_namespaces_are_isolated(self) -> None:
        default = self.storage.for_user(1)
        settings = default.scoped("settings")
        await default.set("language", "ru")
        await settings.set("language", "en")

        self.assertEqual(await default.get("language"), "ru")
        self.assertEqual(await settings.get("language"), "en")

    async def test_increment_is_atomic_for_concurrent_tasks(self) -> None:
        calls = 100
        await asyncio.gather(
            *(self.storage.bot.increment("counter") for _ in range(calls)),
        )

        self.assertEqual(await self.storage.bot.get("counter"), calls)

    async def test_writes_from_two_storage_instances_are_atomic(self) -> None:
        second_storage = PersistentStorage(self.database_url)
        await second_storage.initialize()
        try:
            calls = 50
            await asyncio.gather(
                *(self.storage.bot.increment("shared_counter") for _ in range(calls)),
                *(second_storage.bot.increment("shared_counter") for _ in range(calls)),
            )
            self.assertEqual(
                await self.storage.bot.get("shared_counter"),
                calls * 2,
            )
        finally:
            await second_storage.close()

    async def test_mutate_updates_complex_value(self) -> None:
        user_storage = self.storage.for_user(1)
        result = await user_storage.mutate(
            "inventory",
            lambda items: [*items, "sword"],
            default=[],
        )

        self.assertEqual(result, ["sword"])
        self.assertEqual(await user_storage.get("inventory"), ["sword"])

    async def test_non_json_value_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            await self.storage.bot.set("bad", object())

    async def test_values_survive_storage_restart(self) -> None:
        await self.storage.bot.set("persistent", {"ok": True})
        await self.storage.close()

        self.storage = PersistentStorage(self.database_url)
        await self.storage.initialize()

        self.assertEqual(
            await self.storage.bot.get("persistent"),
            {"ok": True},
        )


if __name__ == "__main__":
    unittest.main()
