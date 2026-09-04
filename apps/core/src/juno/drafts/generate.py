"""Template-generated draft artifacts. Never auto-publish (ADR-09)."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from juno.bot.services import recent_captures
from juno.drafts.kinds import (
    DRAFT_KIND_DOC,
    DRAFT_KIND_FLASHCARD,
    DRAFT_KIND_JOURNAL,
    GENERATOR_TEMPLATE,
)
from juno.graph.db import Database
from juno.hitl.queue import ReviewCard, ReviewQueue
from juno.models import Capture

logger = logging.getLogger("juno.drafts")

SMOKE_LOOKBACK_HOURS = 72


def format_journal_snippet(captures: list[Capture], *, now: datetime | None = None) -> str:
    """One-paragraph journal from capture titles. Deterministic; no LLM."""
    now = now or datetime.now(UTC)
    day = now.strftime("%Y-%m-%d")
    if not captures:
        return (
            f"Journal snippet for {day}. No recent captures yet — "
            "this is a template draft for HITL review only."
        )
    bits: list[str] = []
    for cap in captures[:5]:
        title = (cap.title or cap.uri or cap.text or f"capture #{cap.id}").strip()
        title = " ".join(title.split())[:80]
        bits.append(f"{title} [{cap.source_type}]")
    joined = "; ".join(bits)
    return (
        f"Journal snippet for {day}: recently captured {joined}. "
        "This is a template draft, not a published journal."
    )


def format_flashcard(front: str, back: str) -> tuple[str, dict[str, str]]:
    """Q/A card body plus structured extra. Generation stays template-only."""
    q = " ".join((front or "What stood out?").split())[:240]
    a = " ".join((back or "").split())[:500]
    body = f"Q: {q}\nA: {a or '(empty)'}"
    return body, {"front": q, "back": a}


def format_doc_stub(captures: list[Capture], *, now: datetime | None = None) -> str:
    now = now or datetime.now(UTC)
    day = now.strftime("%Y-%m-%d")
    lines = [f"# Draft README ({day})", "", "Template stub — not a published document."]
    for cap in captures[:5]:
        title = (cap.title or cap.uri or f"capture #{cap.id}").strip()
        title = " ".join(title.split())[:80]
        lines.append(f"- {title} [{cap.source_type}]")
    if len(captures) == 0:
        lines.append("- (no recent captures)")
    return "\n".join(lines)


async def enqueue_journal_draft(
    db: Database,
    *,
    captures: list[Capture] | None = None,
    generator: str = GENERATOR_TEMPLATE,
    lookback_hours: int = SMOKE_LOOKBACK_HOURS,
    now: datetime | None = None,
) -> ReviewCard:
    """Queue a pending journal draft. Approve confirms; it still is not published."""
    now = now or datetime.now(UTC)
    if captures is None:
        captures = await recent_captures(db, since=now - timedelta(hours=lookback_hours), limit=8)
    body = format_journal_snippet(captures, now=now)
    title = f"Journal snippet {now.strftime('%Y-%m-%d')}"
    ids = [cap.id for cap in captures if cap.id is not None]
    return await ReviewQueue(db).propose_draft(
        draft_kind=DRAFT_KIND_JOURNAL,
        title=title,
        body=body,
        source_capture_ids=ids,
        generator=generator,
        reason=(
            "Auto-generated journal snippet. Approve keeps it as a confirmed draft; "
            "it is not published to the graph or Telegram."
        ),
    )


async def enqueue_flashcard_draft(
    db: Database,
    *,
    front: str,
    back: str,
    source_capture_ids: list[int] | None = None,
    title: str | None = None,
    extra: dict[str, Any] | None = None,
    generator: str = GENERATOR_TEMPLATE,
) -> ReviewCard:
    body, structured = format_flashcard(front, back)
    payload_extra = {**structured, **(extra or {})}
    return await ReviewQueue(db).propose_draft(
        draft_kind=DRAFT_KIND_FLASHCARD,
        title=title or structured["front"][:80] or "Flashcard",
        body=body,
        extra=payload_extra,
        source_capture_ids=source_capture_ids,
        generator=generator,
        reason=(
            "Auto-generated flashcard. Approve confirms it into SRS practice; "
            "it is not published to the graph or Telegram as canonical."
        ),
    )


async def enqueue_doc_draft(
    db: Database,
    *,
    captures: list[Capture] | None = None,
    generator: str = GENERATOR_TEMPLATE,
    lookback_hours: int = SMOKE_LOOKBACK_HOURS,
    now: datetime | None = None,
) -> ReviewCard:
    now = now or datetime.now(UTC)
    if captures is None:
        captures = await recent_captures(db, since=now - timedelta(hours=lookback_hours), limit=8)
    body = format_doc_stub(captures, now=now)
    ids = [cap.id for cap in captures if cap.id is not None]
    return await ReviewQueue(db).propose_draft(
        draft_kind=DRAFT_KIND_DOC,
        title=f"README draft {now.strftime('%Y-%m-%d')}",
        body=body,
        source_capture_ids=ids,
        generator=generator,
        reason=(
            "Auto-generated doc draft. Approve keeps it as a confirmed draft; "
            "it is not written to any git repo or published."
        ),
    )


async def maybe_enqueue_smoke_draft(app: Any) -> ReviewCard | None:
    """Spike S5: one draft at serve start when JUNO_DRAFTS_SMOKE is on."""
    from juno.jobs.health import record_polish_health

    settings = getattr(app.state, "settings", None)
    if settings is None or not bool(getattr(settings, "juno_drafts_smoke", False)):
        return None
    db: Database | None = getattr(app.state, "db", None)
    if bool(getattr(app.state, "capture_paused", False)):
        logger.info("drafts smoke skipped — capture paused")
        await record_polish_health(db, detail="drafts smoke skipped (paused)", ok=True)
        return None
    if db is None:
        return None
    generator = getattr(settings, "juno_drafts_generator", GENERATOR_TEMPLATE)
    card = await enqueue_journal_draft(db, generator=generator)
    logger.info("drafts smoke queued review #%s (kind=%s)", card.id, card.kind)
    await record_polish_health(db, detail=f"drafts smoke queued #{card.id}", ok=True)
    return card
