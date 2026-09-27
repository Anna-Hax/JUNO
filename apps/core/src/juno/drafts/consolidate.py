"""Template topic summary queued for /review. Approve does not publish (ADR-09)."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from juno.bot.services import recent_captures
from juno.drafts.kinds import (
    DRAFT_KIND_TOPIC,
    GENERATOR_TEMPLATE,
    STATUS_CONFIRMED,
    STATUS_PENDING,
)
from juno.graph.db import Database
from juno.hitl.queue import ReviewCard, ReviewQueue
from juno.models import Capture, DraftArtifact

logger = logging.getLogger("juno.drafts")

LOOKBACK_DAYS = 7


def _is_time_only(capture: Capture) -> bool:
    raw = capture.raw_json if isinstance(capture.raw_json, dict) else {}
    return raw.get("kind") == "time"


def format_topic_summary(captures: list[Capture], *, now: datetime) -> str:
    day = now.strftime("%Y-%m-%d")
    lines = [
        f"Topic summary for {day}.",
        "",
        "Recent captures:",
    ]
    for cap in captures[:8]:
        title = (cap.title or cap.uri or cap.text or f"capture #{cap.id}").strip()
        title = " ".join(title.split())[:80]
        when = ""
        if cap.captured_at is not None:
            when = cap.captured_at.strftime("%Y-%m-%d")
        stamp = f" {when}" if when else ""
        lines.append(f"- {title} [{cap.source_type}]{stamp}")
    lines.append("")
    lines.append(
        "Template draft for /review. Approve keeps it unpublished; "
        "it is not written into the graph as a new capture."
    )
    return "\n".join(lines)


async def _summary_exists(db: Database, title: str) -> bool:
    async def fetch(session: AsyncSession) -> bool:
        result = await session.execute(
            select(DraftArtifact.id)
            .where(DraftArtifact.kind == DRAFT_KIND_TOPIC)
            .where(DraftArtifact.title == title)
            .where(DraftArtifact.status.in_((STATUS_PENDING, STATUS_CONFIRMED)))
            .limit(1)
        )
        return result.scalar_one_or_none() is not None

    return await db.read(fetch)


async def queue_topic_summary(
    db: Database,
    *,
    paused: bool = False,
    now: datetime | None = None,
) -> ReviewCard | None:
    """Enqueue one topic summary for today. No model call. No-op when paused."""
    if paused:
        logger.info("topic summary skipped — capture paused")
        return None
    current = now or datetime.now(UTC)
    title = f"Topic summary {current.strftime('%Y-%m-%d')}"
    if await _summary_exists(db, title):
        return None
    captures = await recent_captures(
        db, since=current - timedelta(days=LOOKBACK_DAYS), limit=12
    )
    knowledge = [
        cap
        for cap in captures
        if not _is_time_only(cap) and (cap.title or cap.text or cap.uri)
    ]
    if len(knowledge) < 2:
        return None
    body = format_topic_summary(knowledge, now=current)
    ids = [cap.id for cap in knowledge if cap.id is not None]
    return await ReviewQueue(db).propose_draft(
        draft_kind=DRAFT_KIND_TOPIC,
        title=title,
        body=body,
        source_capture_ids=ids,
        generator=GENERATOR_TEMPLATE,
        reason=(
            "Auto-generated topic summary. Approve keeps it as a confirmed draft; "
            "it is not published to the graph."
        ),
    )
