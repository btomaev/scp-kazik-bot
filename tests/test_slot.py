import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from aiogram.enums import ChatType

import config
from handlers import slot


class SlotMessageTests(unittest.IsolatedAsyncioTestCase):
    async def test_loss_message_is_ephemeral_in_supergroup(self) -> None:
        message = SimpleNamespace(
            text='/slot 100',
            chat=SimpleNamespace(type=ChatType.SUPERGROUP),
            from_user=SimpleNamespace(id=42),
            answer=AsyncMock(),
            reply=AsyncMock(),
            reply_dice=AsyncMock(
                return_value=SimpleNamespace(
                    dice=SimpleNamespace(value=2),
                ),
            ),
        )
        user_storage = SimpleNamespace(
            get=AsyncMock(return_value=1_000),
            increment=AsyncMock(),
        )

        with patch('handlers.slot.asyncio.sleep', new=AsyncMock()):
            await slot.slot(message, user_storage)

        message.answer.assert_awaited_once_with(
            config.get('localization.dep.slot.loss'),
            receiver_user_id=42,
        )
        message.reply.assert_not_awaited()


if __name__ == '__main__':
    unittest.main()
