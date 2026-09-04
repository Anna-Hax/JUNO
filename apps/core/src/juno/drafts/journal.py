"""Weekly journal / README drafts from IDE captures. Never write user repos."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from juno.bot.services import recent_captures
from juno.drafts.generate import enqueue_doc_draft, enqueue_journal_draft
from juno.graph.db import Database
from juno.hitl.queue import ReviewCard
from juno.models import Capture

logger = logging.getLogger("juno.drafts")

IDE_LOOKBACK_DAYS = 7


async def recent_ide_captures(
    db: Database,
    *,
    now: datetime | None = None,
    days: int = IDE_LOOKBACK_DAYS,
    limit: int = 20,
) -> list[Capture]:
    now = now or datetime.now(UTC)
    rows = await recent_captures(db, since=now - timedelta(days=days), limit=limit)
    return [row for row in rows if row.source_type == "ide"]


async def queue_ide_journal_draft(
    db: Database,
    *,
    paused: bool = False,
    now: datetime | None = None,
) -> ReviewCard | None:
    if paused:
        logger.info("journal draft skipped — capture paused")
        return None
    captures = await recent_ide_captures(db, now=now)
    return await enqueue_journal_draft(db, captures=captures, now=now)


async def queue_ide_readme_draft(
    db: Database,
    *,
    paused: bool = False,
    now: datetime | None = None,
) -> ReviewCard | None:
    if paused:
        logger.info("readme draft skipped — capture paused")
        return None
    captures = await recent_ide_captures(db, now=now)
    return await enqueue_doc_draft(db, captures=captures, now=now)
