"""Selective prune/archive with mandatory HITL — never silent delete (ADR-12 / #113)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from juno.graph.db import Database
from juno.models import Capture, Chunk, Edge, ReviewItem

PRUNE_CONFIRM_PHRASE = "prune-selected"
STATUS_ARCHIVED = "archived"
STATUS_FAILED = "failed"
STATUS_COMMITTED = "committed"
DEFAULT_MIN_AGE_DAYS = 90
FAILED_MIN_AGE_DAYS = 7
MAX_BATCH = 20
UNUSED_MAX_CHARS = 120


@dataclass(frozen=True)
class PruneCandidate:
    id: int
    title: str | None
    source_type: str
    status: str
    captured_at: datetime | None
    reason: str

    def label(self) -> str:
        title = (self.title or "").strip() or "(untitled)"
        if len(title) > 60:
            title = title[:59].rstrip() + "…"
        return f"#{self.id} [{self.source_type}/{self.status}] {self.reason} — {title}"


def fingerprint(capture_ids: list[int]) -> str:
    return ",".join(str(i) for i in sorted(capture_ids))


def _has_highlights(raw: Any) -> bool:
    if not isinstance(raw, dict):
        return False
    highlights = raw.get("highlights")
    return isinstance(highlights, list) and len(highlights) > 0


def _is_short(text: str | None) -> bool:
    return len((text or "").strip()) <= UNUSED_MAX_CHARS


async def list_prune_candidates(
    db: Database,
    *,
    min_age_days: int = DEFAULT_MIN_AGE_DAYS,
    now: datetime | None = None,
    limit: int = MAX_BATCH,
) -> list[PruneCandidate]:
    """Old unused captures plus aged failed ingest rows. Never includes archived."""
    when = now or datetime.now(UTC)
    if when.tzinfo is None:
        when = when.replace(tzinfo=UTC)
    age_cut = when - timedelta(days=max(1, int(min_age_days)))
    fail_cut = when - timedelta(days=FAILED_MIN_AGE_DAYS)

    async def load(session: AsyncSession) -> list[PruneCandidate]:
        used = {
            int(eid)
            for eid in (
                await session.execute(
                    select(Edge.evidence_capture_id).where(
                        Edge.evidence_capture_id.is_not(None),
                        Edge.status == "committed",
                    )
                )
            ).scalars()
            if eid is not None
        }
        rows = (
            (
                await session.execute(
                    select(Capture)
                    .where(Capture.status != STATUS_ARCHIVED)
                    .order_by(Capture.captured_at.asc())
                )
            )
            .scalars()
            .all()
        )
        out: list[PruneCandidate] = []
        for row in rows:
            captured = row.captured_at
            if captured is not None and captured.tzinfo is None:
                captured = captured.replace(tzinfo=UTC)
            if row.status == STATUS_FAILED:
                if captured is None or captured > fail_cut:
                    continue
                out.append(
                    PruneCandidate(
                        id=row.id,
                        title=row.title,
                        source_type=row.source_type,
                        status=row.status,
                        captured_at=row.captured_at,
                        reason="failed",
                    )
                )
                if len(out) >= limit:
                    break
                continue
            if row.status != STATUS_COMMITTED:
                continue
            if captured is None or captured > age_cut:
                continue
            if row.id in used or _has_highlights(row.raw_json):
                continue
            if not _is_short(row.text):
                continue
            out.append(
                PruneCandidate(
                    id=row.id,
                    title=row.title,
                    source_type=row.source_type,
                    status=row.status,
                    captured_at=row.captured_at,
                    reason="old_unused",
                )
            )
            if len(out) >= limit:
                break
        return out[:limit]

    return await db.read(load)


async def pending_prune_capture_ids(db: Database) -> set[int]:
    from juno.hitl.queue import KIND_PRUNE, STATUS_DECIDED

    async def load(session: AsyncSession) -> set[int]:
        rows = (
            (await session.execute(select(ReviewItem).where(ReviewItem.kind == KIND_PRUNE)))
            .scalars()
            .all()
        )
        ids: set[int] = set()
        for row in rows:
            if row.status == STATUS_DECIDED:
                continue
            payload = row.payload if isinstance(row.payload, dict) else {}
            for raw in payload.get("capture_ids") or []:
                try:
                    ids.add(int(raw))
                except (TypeError, ValueError):
                    continue
        return ids

    return await db.read(load)


def format_candidates(candidates: list[PruneCandidate], *, min_age_days: int) -> str:
    if not candidates:
        failed = FAILED_MIN_AGE_DAYS
        return (
            f"No prune candidates (old unused ≥{min_age_days}d, or failed ≥{failed}d). "
            "Nothing will be deleted."
        )
    lines = [
        (
            f"Prune candidates ({len(candidates)}; "
            f"age ≥{min_age_days}d unused, or failed ≥{FAILED_MIN_AGE_DAYS}d):"
        ),
        *[f"• {c.label()}" for c in candidates],
        (
            "Nothing is deleted until /review Approve "
            "(or `juno prune --confirm prune-selected` then Approve)."
        ),
        "Optional backup: `juno export` first. Distinct from `juno wipe`.",
    ]
    return "\n".join(lines)


async def propose_prune(
    db: Database,
    *,
    candidates: list[PruneCandidate],
    exported_path: str | None = None,
) -> Any:
    """Queue HITL prune. Does not archive. Duplicate pending ids are skipped."""
    from juno.hitl.queue import KIND_PRUNE, ReviewQueue

    pending = await pending_prune_capture_ids(db)
    fresh = [c for c in candidates if c.id not in pending]
    if not fresh:
        return None
    ids = [c.id for c in fresh]
    return await ReviewQueue(db).enqueue(
        kind=KIND_PRUNE,
        confidence=0.3,
        payload={
            "capture_ids": ids,
            "titles": [c.label() for c in fresh],
            "fingerprint": fingerprint(ids),
            "exported_path": exported_path,
            "archived": False,
            "reason": "Selective prune — Approve archives these captures; Reject leaves them.",
        },
    )


async def apply_prune_captures(session: AsyncSession, capture_ids: list[int]) -> list[str]:
    """Archive captures in-session. Returns chroma ids to drop after the write commits."""
    chroma_ids: list[str] = []
    for raw_id in capture_ids:
        cap = await session.get(Capture, int(raw_id))
        if cap is None or cap.status == STATUS_ARCHIVED:
            continue
        cap.status = STATUS_ARCHIVED
        chunks = (
            (await session.execute(select(Chunk).where(Chunk.capture_id == cap.id))).scalars().all()
        )
        for chunk in chunks:
            if chunk.chroma_id:
                chroma_ids.append(chunk.chroma_id)
    return chroma_ids
