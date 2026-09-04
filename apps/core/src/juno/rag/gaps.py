"""Skill-gap flags: repeat IDE errors and unfinished reads. Do not nag."""

from __future__ import annotations

import logging
import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from juno.graph.db import Database
from juno.hitl.queue import KIND_SKILL_GAP, ReviewQueue
from juno.models import AppSetting, Capture

logger = logging.getLogger("juno.gaps")

HIGH_CONFIDENCE = 0.7
MIN_REPEAT = 2
UNFINISHED_DAYS = 3
SEEN_PREFIX = "gaps.seen."


@dataclass(frozen=True)
class SkillGap:
    key: str
    topic: str
    kind: str  # repeat_error | unfinished_read
    count: int
    capture_ids: list[int]
    related: list[str]
    confidence: float

    def seen_key(self) -> str:
        return f"{SEEN_PREFIX}{self.key}"


def topic_key(title: str) -> str:
    words = re.findall(r"[a-z0-9]+", (title or "").lower())
    return " ".join(words[:4]) or "untitled"


def format_gaps(gaps: list[SkillGap]) -> str:
    if not gaps:
        return "No skill-gap flags right now."
    lines = ["Possible skill gaps:"]
    for gap in gaps:
        related = f" Related: {', '.join(gap.related[:3])}." if gap.related else ""
        lines.append(f"• {gap.topic} ({gap.kind}, {gap.count}x, {gap.confidence:.0%}).{related}")
    lines.append("Low-confidence flags go to /review. Juno will not nag about the same gap.")
    return "\n".join(lines)


async def find_skill_gaps(db: Database, *, now: datetime | None = None) -> list[SkillGap]:
    now = now or datetime.now(UTC)
    captures = await _all_captures(db)
    gaps: list[SkillGap] = []
    gaps.extend(_repeat_ide_errors(captures))
    gaps.extend(_unfinished_reads(captures, now=now))
    gaps.sort(key=lambda g: (g.confidence, g.count), reverse=True)
    return gaps[:8]


@dataclass(frozen=True)
class GapApplyResult:
    queued: int
    listed: int
    fresh: tuple[SkillGap, ...]


async def apply_skill_gaps(
    db: Database,
    gaps: list[SkillGap],
    *,
    paused: bool = False,
) -> GapApplyResult:
    """Report high-confidence gaps; queue low-confidence HITL. Skip seen keys (no nag)."""
    queued = 0
    listed = 0
    fresh: list[SkillGap] = []
    if paused:
        logger.info("skill-gap scan skipped — capture paused")
        return GapApplyResult(queued=0, listed=0, fresh=())
    review = ReviewQueue(db)
    for gap in gaps:
        if await _already_seen(db, gap.seen_key()):
            continue
        fresh.append(gap)
        if gap.confidence < HIGH_CONFIDENCE:
            await review.enqueue(
                kind=KIND_SKILL_GAP,
                confidence=gap.confidence,
                payload={
                    "topic": gap.topic,
                    "gap_kind": gap.kind,
                    "count": gap.count,
                    "capture_ids": gap.capture_ids,
                    "related": gap.related,
                    "reason": "Low-confidence skill-gap; confirm it is a real struggle, not noise.",
                    "confirmed": False,
                },
            )
            queued += 1
        else:
            listed += 1
        await _mark_seen(db, gap.seen_key())
    return GapApplyResult(queued=queued, listed=listed, fresh=tuple(fresh))


def _repeat_ide_errors(captures: list[Capture]) -> list[SkillGap]:
    buckets: dict[str, list[Capture]] = defaultdict(list)
    for cap in captures:
        if cap.source_type != "ide":
            continue
        raw = cap.raw_json if isinstance(cap.raw_json, dict) else {}
        kind = str(raw.get("kind") or "")
        title = cap.title or cap.text or ""
        if kind != "cursor_error" and "error" not in title.lower():
            continue
        key = topic_key(title)
        if len(key) < 6:
            continue
        buckets[key].append(cap)
    gaps: list[SkillGap] = []
    for key, rows in buckets.items():
        if len(rows) < MIN_REPEAT:
            continue
        related = _related_titles(captures, key, exclude={r.id for r in rows})
        conf = 0.55 if len(rows) == 2 else 0.8
        gaps.append(
            SkillGap(
                key=f"err.{key}",
                topic=key,
                kind="repeat_error",
                count=len(rows),
                capture_ids=[r.id for r in rows],
                related=related,
                confidence=conf,
            )
        )
    return gaps


def _unfinished_reads(captures: list[Capture], *, now: datetime) -> list[SkillGap]:
    cutoff = now - timedelta(days=UNFINISHED_DAYS)
    by_uri: dict[str, list[Capture]] = defaultdict(list)
    for cap in captures:
        if cap.source_type != "browser" or not cap.uri:
            continue
        by_uri[cap.uri].append(cap)
    gaps: list[SkillGap] = []
    for uri, rows in by_uri.items():
        if len(rows) != 1:
            continue
        cap = rows[0]
        raw = cap.raw_json if isinstance(cap.raw_json, dict) else {}
        highlights = raw.get("highlights") if isinstance(raw.get("highlights"), list) else []
        if highlights:
            continue
        when = cap.captured_at
        if when is None:
            continue
        if when.tzinfo is None:
            when = when.replace(tzinfo=UTC)
        if when > cutoff:
            continue
        title = cap.title or uri
        key = topic_key(title)
        related = _related_titles(captures, key, exclude={cap.id})
        gaps.append(
            SkillGap(
                key=f"read.{cap.id}",
                topic=title[:80],
                kind="unfinished_read",
                count=1,
                capture_ids=[cap.id],
                related=related,
                confidence=0.45,
            )
        )
    return gaps


def _related_titles(captures: list[Capture], key: str, *, exclude: set[int]) -> list[str]:
    tokens = set(key.split())
    found: list[str] = []
    for cap in captures:
        if cap.id in exclude:
            continue
        title = (cap.title or cap.text or "")[:80]
        words = set(re.findall(r"[a-z0-9]+", title.lower()))
        if tokens & words:
            found.append(title or f"capture #{cap.id}")
        if len(found) >= 3:
            break
    return found


async def _all_captures(db: Database) -> list[Capture]:
    async def load(session: AsyncSession) -> list[Capture]:
        result = await session.execute(select(Capture).order_by(Capture.id))
        return list(result.scalars())

    return await db.read(load)


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
