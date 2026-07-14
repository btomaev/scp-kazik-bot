from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, User

from .core import PersistentStorage


class StorageMiddleware(BaseMiddleware):
    """Inject bot-wide and user-bound repositories into aiogram handlers."""

    def __init__(self, storage: PersistentStorage) -> None:
        self.storage = storage

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        data["storage"] = self.storage
        data["bot_storage"] = self.storage.bot

        user = data.get("event_from_user")
        if isinstance(user, User):
            await self.storage.sync_user(
                user.id,
                username=user.username,
                first_name=user.first_name,
                last_name=user.last_name,
                language_code=user.language_code,
                is_bot=user.is_bot,
            )
            data["user_storage"] = self.storage.for_user(user.id)

        return await handler(event, data)
