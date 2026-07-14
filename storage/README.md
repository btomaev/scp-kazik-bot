# Персистентное хранилище

Хранилище работает асинхронно через SQLAlchemy 2 и `aiosqlite`. При старте
бота таблицы создаются автоматически, а при остановке соединения корректно
закрываются. Значениями могут быть любые JSON-совместимые данные: строки,
числа, `bool`, `None`, списки и словари.

Middleware добавляет в обработчик три зависимости:

- `user_storage` — хранилище текущего Telegram-пользователя;
- `bot_storage` — общее хранилище всего бота;
- `storage` — корневой объект, если нужно обратиться к другому пользователю
  или пространству имён.

```python
from aiogram import types

from storage import BotStorage, UserStorage


async def handler(
    message: types.Message,
    user_storage: UserStorage,
    bot_storage: BotStorage,
) -> None:
    await user_storage.set("settings", {"theme": "dark"})
    settings = await user_storage.get("settings", default={})

    user_visits = await user_storage.increment("visits")
    total_visits = await bot_storage.increment("visits")
    await message.answer(f"{settings=}, {user_visits=}, {total_visits=}")
```

Для логического разделения данных есть пространства имён:

```python
profile = user_storage.scoped("profile")
await profile.set_many({"level": 3, "items": ["key", "map"]})

runtime = bot_storage.scoped("runtime")
await runtime.set("maintenance", False)
```

Основные операции: `get`, `exists`, `set`, `set_many`, `delete`, `clear`,
`all`, `increment` и `mutate`. `increment` выполняется атомарно. Для сложного
изменения на основе предыдущего значения используйте `mutate` с быстрой
синхронной функцией:

```python
await user_storage.mutate(
    "inventory",
    lambda items: [*items, "sword"],
    default=[],
)
```

Записи внутри процесса сериализуются через `asyncio.Lock`. Транзакции записи
начинаются с `BEGIN IMMEDIATE`, поэтому конкурирующие процессы не теряют
обновления. SQLite работает в WAL-режиме, с `busy_timeout=30s` и включёнными
внешними ключами. Путь к базе по умолчанию — `data/bot.db`; его можно изменить
через переменную окружения, например:

```dotenv
DATABASE_URL=sqlite+aiosqlite:///data/bot.db
```
