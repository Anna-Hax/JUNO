"""Template-generated journal drafts for Spike S5. Never auto-publish."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from juno.bot.services import recent_captures
from juno.graph.db import Database
from juno.hitl.queue import ReviewCard, ReviewQueue
from juno.models import Capture

logger = logging.getLogger("juno.drafts")

GENERATOR_TEMPLATE = "template"
DRAFT_KIND_JOURNAL = "journal"
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
        generator=generator if generator == GENERATOR_TEMPLATE else GENERATOR_TEMPLATE,
        reason=(
            "Auto-generated journal snippet. Approve keeps it as a confirmed draft; "
            "it is not published to the graph or Telegram."
        ),
    )


async def maybe_enqueue_smoke_draft(app: Any) -> ReviewCard | None:
    """Spike S5: one draft at serve start when JUNO_DRAFTS_SMOKE is on."""
    settings = getattr(app.state, "settings", None)
    if settings is None or not bool(getattr(settings, "juno_drafts_smoke", False)):
        return None
    if bool(getattr(app.state, "capture_paused", False)):
        logger.info("drafts smoke skipped — capture paused")
        return None
    db: Database | None = getattr(app.state, "db", None)
    if db is None:
        return None
    generator = getattr(settings, "juno_drafts_generator", GENERATOR_TEMPLATE)
    card = await enqueue_journal_draft(db, generator=generator)
    logger.info("drafts smoke queued review #%s (kind=%s)", card.id, card.kind)
    return card
