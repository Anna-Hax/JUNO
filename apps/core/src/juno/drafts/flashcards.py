"""Flashcards from highlights + SM-2-lite SRS. Drafts stay HITL until approve."""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from juno.drafts.generate import enqueue_flashcard_draft
from juno.drafts.kinds import DRAFT_KIND_FLASHCARD, STATUS_CONFIRMED, STATUS_PENDING
from juno.graph.db import Database
from juno.hitl.queue import ReviewCard
from juno.models import Capture, DraftArtifact, Flashcard

logger = logging.getLogger("juno.drafts")

AGAIN_DELAY = timedelta(minutes=10)
MIN_HIGHLIGHT_LEN = 8


@dataclass(frozen=True)
class Highlight:
    capture_id: int
    text: str
    back: str
    fingerprint: str


def highlight_fingerprint(capture_id: int, text: str) -> str:
    norm = " ".join((text or "").lower().split())
    digest = hashlib.sha256(f"{capture_id}:{norm}".encode()).hexdigest()[:20]
    return f"hl.{capture_id}.{digest}"


def extract_highlights(capture: Capture) -> list[Highlight]:
    raw = capture.raw_json if isinstance(capture.raw_json, dict) else {}
    items = raw.get("highlights") if isinstance(raw.get("highlights"), list) else []
    back = (capture.title or capture.uri or capture.source_type or "").strip()
    found: list[Highlight] = []
    seen: set[str] = set()
    for item in items:
        if isinstance(item, str):
            text = item.strip()
        elif isinstance(item, dict):
            text = str(item.get("text") or "").strip()
        else:
            continue
        text = " ".join(text.split())
        if len(text) < MIN_HIGHLIGHT_LEN:
            continue
        fp = highlight_fingerprint(capture.id, text)
        if fp in seen:
            continue
        seen.add(fp)
        found.append(Highlight(capture_id=capture.id, text=text, back=back, fingerprint=fp))
    return found


async def queue_highlight_flashcards(
    db: Database,
    *,
    paused: bool = False,
) -> list[ReviewCard]:
    """Enqueue HITL flashcard drafts from capture highlights. No-op when paused."""
    if paused:
        logger.info("flashcard generation skipped — capture paused")
        return []
    captures = await _captures_with_raw(db)
    known = await _known_fingerprints(db)
    queued: list[ReviewCard] = []
    for cap in captures:
        for hl in extract_highlights(cap):
            if hl.fingerprint in known:
                continue
            card = await enqueue_flashcard_draft(
                db,
                front=hl.text,
                back=hl.back,
                source_capture_ids=[hl.capture_id],
                title=hl.text[:80],
                extra={"fingerprint": hl.fingerprint, "capture_id": hl.capture_id},
            )
            known.add(hl.fingerprint)
            queued.append(card)
    return queued


async def next_due_card(db: Database, *, now: datetime | None = None) -> Flashcard | None:
    now = now or datetime.now(UTC)

    async def load(session: AsyncSession) -> Flashcard | None:
        stmt = (
            select(Flashcard)
            .where(Flashcard.due_at <= now)
            .order_by(Flashcard.due_at, Flashcard.id)
            .limit(1)
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    return await db.read(load)


def apply_again(card: Flashcard, *, now: datetime | None = None) -> None:
    now = now or datetime.now(UTC)
    card.reps = 0
    card.interval_days = 0
    card.ease = max(1.3, float(card.ease) - 0.2)
    card.due_at = now + AGAIN_DELAY


def apply_good(card: Flashcard, *, now: datetime | None = None) -> None:
    now = now or datetime.now(UTC)
    card.reps = int(card.reps) + 1
    if card.reps == 1:
        card.interval_days = 1
    elif card.reps == 2:
        card.interval_days = 6
    else:
        card.interval_days = max(1, round(float(card.interval_days) * float(card.ease)))
    card.ease = min(2.8, float(card.ease) + 0.05)
    card.due_at = now + timedelta(days=card.interval_days)


async def review_card(db: Database, card_id: int, grade: str) -> Flashcard:
    if grade not in {"again", "good"}:
        raise ValueError(f"unknown grade: {grade}")

    async def write(session: AsyncSession) -> Flashcard:
        row = await session.get(Flashcard, card_id)
        if row is None:
            raise LookupError(f"flashcard {card_id} not found")
        now = datetime.now(UTC)
        if grade == "again":
            apply_again(row, now=now)
        else:
            apply_good(row, now=now)
        return row

    return await db.write(write)


async def activate_approved_flashcard(
    session: AsyncSession, artifact: DraftArtifact
) -> Flashcard | None:
    """Create an SRS row after HITL approve. Never called for unpublished drafts."""
    if artifact.kind != DRAFT_KIND_FLASHCARD:
        return None
    extra = artifact.extra_json if isinstance(artifact.extra_json, dict) else {}
    front = str(extra.get("front") or artifact.title or "").strip()
    back = str(extra.get("back") or "").strip()
    fingerprint = str(extra.get("fingerprint") or highlight_fingerprint(0, front))
    capture_id = extra.get("capture_id")
    existing = await session.execute(select(Flashcard).where(Flashcard.artifact_id == artifact.id))
    row = existing.scalar_one_or_none()
    if row is not None:
        return row
    by_fp = await session.execute(select(Flashcard).where(Flashcard.fingerprint == fingerprint))
    if by_fp.scalar_one_or_none() is not None:
        return None
    card = Flashcard(
        artifact_id=artifact.id,
        front=front or artifact.body,
        back=back,
        fingerprint=fingerprint,
        capture_id=int(capture_id) if capture_id is not None else None,
        due_at=datetime.now(UTC),
        ease=2.5,
        interval_days=0,
        reps=0,
    )
    session.add(card)
    await session.flush()
    return card


def format_card_prompt(card: Flashcard) -> str:
    return f"Flashcard #{card.id}\n\nQ: {card.front}"


def format_card_reveal(card: Flashcard) -> str:
    return f"A: {card.back or '(empty)'}"


async def _captures_with_raw(db: Database) -> list[Capture]:
    async def load(session: AsyncSession) -> list[Capture]:
        result = await session.execute(
            select(Capture).where(Capture.raw_json.is_not(None)).order_by(Capture.id)
        )
        return list(result.scalars())

    return await db.read(load)


async def _known_fingerprints(db: Database) -> set[str]:
    async def load(session: AsyncSession) -> set[str]:
        known: set[str] = set()
        cards = await session.execute(select(Flashcard.fingerprint))
        known.update(str(x) for x in cards.scalars())
        arts = await session.execute(
            select(DraftArtifact).where(
                DraftArtifact.kind == DRAFT_KIND_FLASHCARD,
                DraftArtifact.status.in_((STATUS_PENDING, STATUS_CONFIRMED)),
            )
        )
        for art in arts.scalars():
            extra = art.extra_json if isinstance(art.extra_json, dict) else {}
            fp = extra.get("fingerprint")
            if fp:
                known.add(str(fp))
        return known

    return await db.read(load)
