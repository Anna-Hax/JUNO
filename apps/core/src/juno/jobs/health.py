"""Persist scheduler freshness on module_health.jobs (ADR-02 writes)."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from juno.graph.db import Database
from juno.models import ModuleHealth

JOBS_MODULE = "jobs"


async def record_jobs_health(
    db: Database | None,
    *,
    detail: str,
    ok: bool = True,
    error: str | None = None,
) -> None:
    if db is None:
        return

    async def write(session: AsyncSession) -> None:
        row = await session.get(ModuleHealth, JOBS_MODULE)
        if row is None:
            row = ModuleHealth(module=JOBS_MODULE)
            session.add(row)
        now = datetime.now(UTC)
        row.detail = detail
        if ok:
            row.last_success_at = now
            row.last_error = None
        else:
            row.last_error_at = now
            row.last_error = (error or "job failed")[:500]

    await db.write(write)
