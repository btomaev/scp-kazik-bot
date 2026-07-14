from __future__ import annotations

import asyncio
import copy
import inspect
import json
import math
from collections.abc import Callable, Mapping
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, TypeVar

from sqlalchemy import case, delete, event, func, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import (
    AsyncConnection,
    AsyncEngine,
    create_async_engine,
)

from .models import Base, BotValue, TelegramUser, UserValue


T = TypeVar("T")


def _serialize_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
    )


def _validate_json(value: Any) -> None:
    try:
        _serialize_json(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise ValueError("value must be valid JSON data") from error


def _validate_name(value: str, *, name: str, max_length: int) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    if not value:
        raise ValueError(f"{name} cannot be empty")
    if len(value) > max_length:
        raise ValueError(f"{name} cannot be longer than {max_length} characters")
    return value


class PersistentStorage:
    """Async SQLAlchemy storage backed by a local SQLite database."""

    def __init__(
        self,
        database_url: str,
        *,
        busy_timeout_ms: int = 30_000,
    ) -> None:
        url = make_url(database_url)
        if url.drivername != "sqlite+aiosqlite":
            raise ValueError("database_url must use the sqlite+aiosqlite driver")
        if busy_timeout_ms <= 0:
            raise ValueError("busy_timeout_ms must be positive")

        if url.database and url.database != ":memory:":
            Path(url.database).expanduser().parent.mkdir(parents=True, exist_ok=True)

        self._busy_timeout_ms = busy_timeout_ms
        self._engine: AsyncEngine = create_async_engine(
            url,
            connect_args={"timeout": busy_timeout_ms / 1000},
            json_serializer=_serialize_json,
        )
        self._write_lock = asyncio.Lock()
        self._initialization_lock = asyncio.Lock()
        self._initialized = False
        self._closed = False
        self.bot = BotStorage(self)

        self._configure_sqlite_connections()

    @property
    def engine(self) -> AsyncEngine:
        return self._engine

    def _configure_sqlite_connections(self) -> None:
        busy_timeout_ms = self._busy_timeout_ms

        @event.listens_for(self._engine.sync_engine, "connect")
        def set_sqlite_pragmas(dbapi_connection: Any, _: Any) -> None:
            cursor = dbapi_connection.cursor()
            try:
                cursor.execute("PRAGMA foreign_keys=ON")
                cursor.execute(f"PRAGMA busy_timeout={busy_timeout_ms}")
                cursor.execute("PRAGMA journal_mode=WAL")
                cursor.execute("PRAGMA synchronous=NORMAL")
            finally:
                cursor.close()

    async def initialize(self) -> None:
        """Create missing tables. Safe to call more than once."""
        async with self._initialization_lock:
            if self._initialized:
                return
            if self._closed:
                raise RuntimeError("storage is already closed")

            async with self._engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            self._initialized = True

    async def close(self) -> None:
        if self._closed:
            return
        async with self._write_lock:
            await self._engine.dispose()
            self._closed = True
            self._initialized = False

    async def __aenter__(self) -> PersistentStorage:
        await self.initialize()
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.close()

    def for_user(self, user_id: int, namespace: str = "default") -> UserStorage:
        if not isinstance(user_id, int) or isinstance(user_id, bool):
            raise TypeError("user_id must be an integer")
        return UserStorage(self, user_id, namespace)

    def for_bot(self, namespace: str = "default") -> BotStorage:
        if namespace == "default":
            return self.bot
        return BotStorage(self, namespace)

    async def sync_user(
        self,
        user_id: int,
        *,
        username: str | None = None,
        first_name: str | None = None,
        last_name: str | None = None,
        language_code: str | None = None,
        is_bot: bool = False,
    ) -> None:
        """Create or refresh a Telegram user record."""
        if not isinstance(user_id, int) or isinstance(user_id, bool):
            raise TypeError("user_id must be an integer")

        statement = sqlite_insert(TelegramUser).values(
            id=user_id,
            username=username,
            first_name=first_name,
            last_name=last_name,
            language_code=language_code,
            is_bot=is_bot,
        )
        statement = statement.on_conflict_do_update(
            index_elements=[TelegramUser.id],
            set_={
                "username": statement.excluded.username,
                "first_name": statement.excluded.first_name,
                "last_name": statement.excluded.last_name,
                "language_code": statement.excluded.language_code,
                "is_bot": statement.excluded.is_bot,
                "last_seen_at": func.current_timestamp(),
            },
        )
        async with self._write_connection() as connection:
            await connection.execute(statement)

    def _ensure_ready(self) -> None:
        if not self._initialized or self._closed:
            raise RuntimeError("storage is not initialized")

    @asynccontextmanager
    async def _read_connection(self):
        self._ensure_ready()
        async with self._engine.connect() as connection:
            yield connection

    @asynccontextmanager
    async def _write_connection(self):
        """Serialize local writes and reserve SQLite's writer lock up front."""
        self._ensure_ready()
        async with self._write_lock:
            async with self._engine.connect() as connection:
                await connection.exec_driver_sql("BEGIN IMMEDIATE")
                try:
                    yield connection
                except BaseException:
                    await connection.rollback()
                    raise
                else:
                    await connection.commit()


class _KeyValueStorage:
    _model: type[BotValue] | type[UserValue]

    def __init__(self, storage: PersistentStorage, namespace: str) -> None:
        self._storage = storage
        self.namespace = _validate_name(
            namespace,
            name="namespace",
            max_length=64,
        )

    def _identity(self, key: str) -> dict[str, Any]:
        return {
            "namespace": self.namespace,
            "key": _validate_name(key, name="key", max_length=255),
        }

    async def _prepare_value_write(self, connection: AsyncConnection) -> None:
        pass

    async def get(self, key: str, default: T | None = None) -> Any | T | None:
        identity = self._identity(key)
        statement = select(self._model.key, self._model.value).filter_by(**identity)
        async with self._storage._read_connection() as connection:
            result = await connection.execute(statement)
            row = result.one_or_none()
        return default if row is None else row.value

    async def exists(self, key: str) -> bool:
        identity = self._identity(key)
        statement = select(self._model.key).filter_by(**identity).limit(1)
        async with self._storage._read_connection() as connection:
            result = await connection.execute(statement)
            return result.scalar_one_or_none() is not None

    async def set(self, key: str, value: Any) -> None:
        identity = self._identity(key)
        _validate_json(value)
        statement = self._upsert_statement({**identity, "value": value})
        async with self._storage._write_connection() as connection:
            await self._prepare_value_write(connection)
            await connection.execute(statement)

    async def set_many(self, values: Mapping[str, Any]) -> None:
        if not values:
            return

        rows: list[dict[str, Any]] = []
        for key, value in values.items():
            _validate_json(value)
            rows.append({**self._identity(key), "value": value})

        statement = sqlite_insert(self._model).values(rows)
        statement = statement.on_conflict_do_update(
            index_elements=self._conflict_columns,
            set_={
                "value": statement.excluded.value,
                "updated_at": func.current_timestamp(),
            },
        )
        async with self._storage._write_connection() as connection:
            await self._prepare_value_write(connection)
            await connection.execute(statement)

    async def delete(self, key: str) -> bool:
        statement = delete(self._model).filter_by(**self._identity(key))
        async with self._storage._write_connection() as connection:
            result = await connection.execute(statement)
            return result.rowcount > 0

    async def clear(self) -> int:
        statement = delete(self._model).filter_by(**self._scope_identity)
        async with self._storage._write_connection() as connection:
            result = await connection.execute(statement)
            return result.rowcount

    async def all(self) -> dict[str, Any]:
        statement = (
            select(self._model.key, self._model.value)
            .filter_by(**self._scope_identity)
            .order_by(self._model.key)
        )
        async with self._storage._read_connection() as connection:
            result = await connection.execute(statement)
            return dict(result.all())

    async def increment(self, key: str, amount: int | float = 1) -> int | float:
        """Atomically increment a numeric value and return the new value."""
        if (
            not isinstance(amount, (int, float))
            or isinstance(amount, bool)
            or not math.isfinite(amount)
        ):
            raise ValueError("amount must be a finite number")

        identity = self._identity(key)
        statement = sqlite_insert(self._model).values(
            **identity,
            value=amount,
        )
        current_value = self._model.value
        numeric_value = func.json_extract(current_value, "$") + amount
        statement = statement.on_conflict_do_update(
            index_elements=self._conflict_columns,
            set_={
                "value": case(
                    (
                        func.json_type(current_value, "$").in_(("integer", "real")),
                        func.json(numeric_value),
                    ),
                    else_=current_value,
                ),
                "updated_at": func.current_timestamp(),
            },
        ).returning(self._model.value)

        async with self._storage._write_connection() as connection:
            await self._prepare_value_write(connection)
            result = await connection.execute(statement)
            value = result.scalar_one()
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                raise TypeError(f"value stored at {key!r} is not a number")
        return value

    async def mutate(
        self,
        key: str,
        transform: Callable[[Any], Any],
        *,
        default: Any = None,
    ) -> Any:
        """Atomically read, transform and write one value.

        ``transform`` must be a fast synchronous function. The transaction uses
        ``BEGIN IMMEDIATE``, so it is also safe against another local process.
        """
        if not callable(transform):
            raise TypeError("transform must be callable")
        identity = self._identity(key)

        async with self._storage._write_connection() as connection:
            await self._prepare_value_write(connection)
            result = await connection.execute(
                select(self._model.key, self._model.value).filter_by(**identity),
            )
            row = result.one_or_none()
            current = copy.deepcopy(default) if row is None else row.value

            new_value = transform(copy.deepcopy(current))
            if inspect.isawaitable(new_value):
                if inspect.iscoroutine(new_value):
                    new_value.close()
                raise TypeError("transform must be synchronous")
            _validate_json(new_value)
            await connection.execute(
                self._upsert_statement({**identity, "value": new_value}),
            )
            return new_value

    def _upsert_statement(self, values: dict[str, Any]):
        statement = sqlite_insert(self._model).values(**values)
        return statement.on_conflict_do_update(
            index_elements=self._conflict_columns,
            set_={
                "value": statement.excluded.value,
                "updated_at": func.current_timestamp(),
            },
        )

    @property
    def _conflict_columns(self) -> list[Any]:
        raise NotImplementedError

    @property
    def _scope_identity(self) -> dict[str, Any]:
        return {"namespace": self.namespace}


class BotStorage(_KeyValueStorage):
    """Namespace-scoped storage shared by the entire bot."""

    _model = BotValue

    def __init__(
        self,
        storage: PersistentStorage,
        namespace: str = "default",
    ) -> None:
        super().__init__(storage, namespace)

    def scoped(self, namespace: str) -> BotStorage:
        return BotStorage(self._storage, namespace)

    @property
    def _conflict_columns(self) -> list[Any]:
        return [BotValue.namespace, BotValue.key]


class UserStorage(_KeyValueStorage):
    """Namespace-scoped storage bound to one Telegram user ID."""

    _model = UserValue

    def __init__(
        self,
        storage: PersistentStorage,
        user_id: int,
        namespace: str = "default",
    ) -> None:
        self.user_id = user_id
        super().__init__(storage, namespace)

    def scoped(self, namespace: str) -> UserStorage:
        return UserStorage(self._storage, self.user_id, namespace)

    def _identity(self, key: str) -> dict[str, Any]:
        return {"user_id": self.user_id, **super()._identity(key)}

    async def _prepare_value_write(self, connection: AsyncConnection) -> None:
        statement = sqlite_insert(TelegramUser).values(id=self.user_id)
        await connection.execute(statement.on_conflict_do_nothing())

    @property
    def _conflict_columns(self) -> list[Any]:
        return [UserValue.user_id, UserValue.namespace, UserValue.key]

    @property
    def _scope_identity(self) -> dict[str, Any]:
        return {"user_id": self.user_id, "namespace": self.namespace}
