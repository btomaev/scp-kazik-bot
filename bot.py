import asyncio

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.types import BotCommand, BotCommandScopeAllGroupChats

import handlers
import config
from storage import PersistentStorage, StorageMiddleware


def setup_handlers(dp: Dispatcher) -> None:
    dp.include_router(handlers.prepare_router())


async def setup_commands(bot: Bot) -> None:
    await bot.set_my_commands(
        commands=[
            BotCommand(
                command='blackjack',
                description='Запустить игру в блэкджек',
            )
        ],
        scope=BotCommandScopeAllGroupChats(),
    )


async def on_startup(persistence: PersistentStorage) -> None:
    await persistence.initialize()


async def on_shutdown(persistence: PersistentStorage) -> None:
    await persistence.close()


def main() -> None:
    bot = Bot(
        config.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode='HTML'),
    )

    persistence = PersistentStorage(config.DATABASE_URL)
    dp = Dispatcher(persistence=persistence)
    dp.update.outer_middleware(StorageMiddleware(persistence))
    setup_handlers(dp)

    dp.startup.register(on_startup)
    dp.startup.register(setup_commands)
    dp.shutdown.register(on_shutdown)
    asyncio.run(dp.start_polling(bot))


if __name__ == '__main__':
    main()
