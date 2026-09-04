"""Contextual resurfacing: push when an older capture matches something recent."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from juno.bot.services import recent_captures
from juno.graph.db import Database
from juno.hitl.queue import KIND_RESURFACE, ReviewQueue
from juno.models import AppSetting, Capture
from juno.rag.engine import retrieve

logger = logging.getLogger("juno.jobs")

HIGH_CONFIDENCE = 0.55
RECENT_HOURS = 48
STALE_DAYS = 7


@dataclass(frozen=True)
class ResurfaceCandidate:
    recent_id: int
    past_id: int
    score: float
    recent_title: str
    past_title: str
    past_source: str
    past_when: datetime | None
    snippet: str

    def seen_key(self) -> str:
        a, b = sorted((self.recent_id, self.past_id))
        return f"jobs.resurface.seen.{a}.{b}"


def format_resurface_push(candidate: ResurfaceCandidate) -> str:
    when = ""
    if candidate.past_when is not None:
        when = candidate.past_when.strftime("%Y-%m-%d")
    earlier = f"{candidate.past_title} [{candidate.past_source}"
    if when:
        earlier += f" {when}"
    earlier += "]"
    return (
        "This came up again — here's what you know:\n"
        f"Now: {candidate.recent_title}\n"
        f"Earlier: {earlier}\n"
        f"Confidence: {candidate.score:.0%}"
    )


async def find_resurface_candidates(
    db: Database,
    vectors: Any,
    *,
    now: datetime | None = None,
    recent_hours: int = RECENT_HOURS,
    stale_days: int = STALE_DAYS,
) -> list[ResurfaceCandidate]:
    if vectors is None:
        return []
    now = now or datetime.now(UTC)
    recent = await recent_captures(db, since=now - timedelta(hours=recent_hours), limit=12)
    stale_before = now - timedelta(days=stale_days)
    found: list[ResurfaceCandidate] = []
    seen_pairs: set[tuple[int, int]] = set()
    for cap in recent:
        query = (cap.text or cap.title or "").strip()[:240]
        if len(query) < 8:
            continue
        hits = await retrieve(query, vectors=vectors, db=db, n_results=6)
        for hit in hits:
            past_id = hit.capture_id
            if past_id is None or past_id == cap.id:
                continue
            pair = (min(cap.id, past_id), max(cap.id, past_id))
            if pair in seen_pairs:
                continue
            past = await _load_capture(db, past_id)
            if past is None or past.captured_at is None:
                continue
            past_at = past.captured_at
            if past_at.tzinfo is None:
                past_at = past_at.replace(tzinfo=UTC)
            if past_at > stale_before:
                continue
            seen_pairs.add(pair)
            found.append(
                ResurfaceCandidate(
                    recent_id=cap.id,
                    past_id=past.id,
                    score=float(hit.score),
                    recent_title=(cap.title or cap.uri or f"capture #{cap.id}"),
                    past_title=(past.title or past.uri or f"capture #{past.id}"),
                    past_source=past.source_type,
                    past_when=past_at,
                    snippet=(hit.text or "")[:180],
                )
            )
            break
    found.sort(key=lambda c: c.score, reverse=True)
    return found[:5]


async def apply_resurface_candidates(
    app: Any,
    candidates: list[ResurfaceCandidate],
) -> dict[str, int]:
    from juno.jobs.scheduler import send_allowlisted_push

    pushed = 0
    queued = 0
    if not candidates:
        return {"pushed": 0, "queued": 0}
    if bool(getattr(app.state, "capture_paused", False)):
        logger.info("resurfacing skipped — capture paused")
        return {"pushed": 0, "queued": 0}
    db: Database | None = getattr(app.state, "db", None)
    settings = getattr(app.state, "settings", None)
    if db is None or settings is None:
        return {"pushed": 0, "queued": 0}
    ptb = getattr(app.state, "ptb", None)
    bot = getattr(ptb, "bot", None) if ptb is not None else None
    review = ReviewQueue(db)
    for candidate in candidates:
        if await _already_seen(db, candidate.seen_key()):
            continue
        if candidate.score >= HIGH_CONFIDENCE:
            sent = await send_allowlisted_push(
                bot,
                settings,
                format_resurface_push(candidate),
                is_paused=lambda: bool(getattr(app.state, "capture_paused", False)),
            )
            if sent:
                pushed += 1
            await _mark_seen(db, candidate.seen_key())
        else:
            await review.enqueue(
                kind=KIND_RESURFACE,
                confidence=candidate.score,
                payload={
                    "recent_id": candidate.recent_id,
                    "past_id": candidate.past_id,
                    "recent_title": candidate.recent_title,
                    "past_title": candidate.past_title,
                    "reason": "Low-confidence resurface; confirm it is the same topic.",
                    "snippet": candidate.snippet,
                },
            )
            queued += 1
            await _mark_seen(db, candidate.seen_key())
    return {"pushed": pushed, "queued": queued}


async def _load_capture(db: Database, capture_id: int) -> Capture | None:
    async def fn(session: AsyncSession) -> Capture | None:
        return await session.get(Capture, capture_id)

    return await db.read(fn)


async def _already_seen(db: Database, key: str) -> bool:
    async def fn(session: AsyncSession) -> bool:
        row = await session.get(AppSetting, key)
        return row is not None

    return await db.read(fn)


async def _mark_seen(db: Database, key: str) -> None:
    async def fn(session: AsyncSession) -> None:
        row = await session.get(AppSetting, key)
        if row is None:
            session.add(AppSetting(key=key, value="true"))

    await db.write(fn)
