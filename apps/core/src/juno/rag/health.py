"""Operator warnings when a live source is not actually storing captures."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from juno.graph.db import Database
from juno.models import Capture, ModuleHealth

_FRESH = timedelta(days=2)
_WINDOW = timedelta(days=7)

STUB_FALLBACK_WARNING = "Embedder fell back to the stub, so search is not matching meaning."
EMPTY_EXTENSION_WARNING = (
    "Extension heartbeat is fresh, but no captures landed in the last 7 days."
)


def warning_lines(
    *,
    embedding_fallback: bool,
    extension_last_success: datetime | None,
    captures_in_window: int,
    now: datetime,
) -> list[str]:
    lines: list[str] = []
    if embedding_fallback:
        lines.append(STUB_FALLBACK_WARNING)
    if extension_last_success is None or captures_in_window > 0:
        return lines
    last = extension_last_success
    if last.tzinfo is None:
        last = last.replace(tzinfo=UTC)
    current = now if now.tzinfo is not None else now.replace(tzinfo=UTC)
    if current - last <= _FRESH:
        lines.append(EMPTY_EXTENSION_WARNING)
    return lines


async def status_warnings(
    db: Database | None,
    *,
    embedding_fallback: bool,
    now: datetime | None = None,
) -> list[str]:
    current = now or datetime.now(UTC)
    if db is None:
        return warning_lines(
            embedding_fallback=embedding_fallback,
            extension_last_success=None,
            captures_in_window=1,
            now=current,
        )

    async def load(session: AsyncSession) -> tuple[datetime | None, int]:
        row = await session.get(ModuleHealth, "extension")
        since = current - _WINDOW
        result = await session.execute(
            select(func.count())
            .select_from(Capture)
            .where(Capture.captured_at >= since)
            .where(Capture.status != "archived")
        )
        last = row.last_success_at if row is not None else None
        return last, int(result.scalar_one())

    last_success, count = await db.read(load)
    return warning_lines(
        embedding_fallback=embedding_fallback,
        extension_last_success=last_success,
        captures_in_window=count,
        now=current,
    )
