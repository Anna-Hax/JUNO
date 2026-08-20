"""Database engine, sessions, and serialized write queue."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import TypeVar

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from juno.config import Settings
from juno.models import Base

T = TypeVar("T")


class Database:
    """Async SQLite access with WAL and a single-writer queue (ADR-02)."""

    def __init__(self, settings: Settings) -> None:
        settings.juno_data_dir.mkdir(parents=True, exist_ok=True)
        url = f"sqlite+aiosqlite:///{settings.sqlite_path.as_posix()}"
        self.engine = create_async_engine(url, echo=False)
        self.session_factory = async_sessionmaker(self.engine, expire_on_commit=False)
        self._write_lock = asyncio.Lock()

        @event.listens_for(self.engine.sync_engine, "connect")
        def _set_sqlite_pragma(dbapi_connection, connection_record) -> None:  # noqa: ANN001
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA busy_timeout=5000")
            cursor.close()

    async def create_all(self) -> None:
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            await conn.execute(text("PRAGMA journal_mode=WAL"))

    async def write(self, fn: Callable[[AsyncSession], Awaitable[T]]) -> T:
        """Serialize all write transactions through one lock."""
        async with self._write_lock:
            async with self.session_factory() as session:
                async with session.begin():
                    return await fn(session)

    async def read(self, fn: Callable[[AsyncSession], Awaitable[T]]) -> T:
        async with self.session_factory() as session:
            return await fn(session)

    async def dispose(self) -> None:
        await self.engine.dispose()
