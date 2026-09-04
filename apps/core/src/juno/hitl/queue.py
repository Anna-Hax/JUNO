"""Review queue: proposed merges stay pending until an Approve tap."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal

from sqlalchemy import case, select
from sqlalchemy.ext.asyncio import AsyncSession

from juno.graph.db import Database
from juno.models import DraftArtifact, Edge, Node, ReviewItem

Decision = Literal["approve", "reject", "skip"]

KIND_MERGE = "merge"
KIND_ERROR_MATCH = "error_match"
KIND_IDE_BATCH = "ide_batch"
KIND_MOBILE_BATCH = "mobile_batch"
KIND_RESURFACE = "resurface"
KIND_DRAFT = "draft"
STATUS_PENDING = "pending"
STATUS_SKIPPED = "skipped"
STATUS_DECIDED = "decided"
EDGE_PENDING = "pending"
EDGE_COMMITTED = "committed"
EDGE_REJECTED = "rejected"

_ALLOWED_DECISIONS: frozenset[str] = frozenset({"approve", "reject", "skip"})


@dataclass(frozen=True)
class ReviewCard:
    id: int
    kind: str
    confidence: float
    payload: dict[str, Any]
    status: str
    decision: str | None

    def summary(self) -> str:
        lines = [
            f"Review #{self.id} · {self.kind}",
            f"Confidence: {self.confidence:.2f}",
        ]
        if self.kind == KIND_MERGE:
            src = str(self.payload.get("from_name") or "?")
            dst = str(self.payload.get("to_name") or "?")
            lines.append(f'Merge "{src}" → "{dst}"')
            reason = self.payload.get("reason")
            if reason:
                lines.append(str(reason))
            lines.append("This merge stays pending until you Approve.")
        elif self.kind == KIND_ERROR_MATCH:
            new_title = str(self.payload.get("new_title") or "new error")
            past_title = str(self.payload.get("past_title") or "past error")
            lines.append(f'Is this the same root cause?\nNew: "{new_title}"\nPast: "{past_title}"')
            reason = self.payload.get("reason")
            if reason:
                lines.append(str(reason))
            lines.append("Approve only if it is the same root cause, not just a similar stack.")
        elif self.kind == KIND_IDE_BATCH:
            n = self.payload.get("capture_ids") or []
            count = len(n) if isinstance(n, list) else 0
            title = str(self.payload.get("title") or "IDE chat batch")
            lines.append(f"Review sensitive/bulk IDE sync: {title} ({count} capture(s)).")
            reason = self.payload.get("reason")
            if reason:
                lines.append(str(reason))
            lines.append("Approve to keep this batch in the graph; Reject to leave it unconfirmed.")
        elif self.kind == KIND_MOBILE_BATCH:
            n = self.payload.get("capture_ids") or []
            count = len(n) if isinstance(n, list) else 0
            title = str(self.payload.get("title") or "mobile capture")
            lines.append(f"Review phone/Telegram capture: {title} ({count} capture(s)).")
            reason = self.payload.get("reason")
            if reason:
                lines.append(str(reason))
            lines.append(
                "Approve to keep this mobile batch in the graph; Reject if it should not stay."
            )
        elif self.kind == KIND_RESURFACE:
            recent = str(self.payload.get("recent_title") or "recent")
            past = str(self.payload.get("past_title") or "earlier")
            lines.append(f'This came up again?\nNow: "{recent}"\nEarlier: "{past}"')
            reason = self.payload.get("reason")
            if reason:
                lines.append(str(reason))
            lines.append("Approve if it is the same topic; Reject to ignore this suggestion.")
        elif self.kind == KIND_DRAFT:
            title = str(self.payload.get("title") or "draft")
            draft_kind = str(self.payload.get("draft_kind") or "artifact")
            lines.append(f"Draft {draft_kind}: {title}")
            body = str(self.payload.get("body") or "").strip()
            if body:
                lines.append(body[:500])
            reason = self.payload.get("reason")
            if reason:
                lines.append(str(reason))
            lines.append("This draft is not published. Approve to keep it; Reject to discard.")
        else:
            preview = str(self.payload)[:500]
            if preview:
                lines.append(preview)
        return "\n".join(lines)


@dataclass(frozen=True)
class DecideResult:
    card: ReviewCard
    applied: bool
    already_decided: bool
    next_card: ReviewCard | None


class ReviewQueue:
    """Persist HITL items and apply merge payloads only on approve."""

    def __init__(self, db: Database) -> None:
        self.db = db

    async def enqueue(
        self,
        *,
        kind: str,
        payload: dict[str, Any],
        confidence: float = 0.5,
    ) -> ReviewCard:
        async def write(session: AsyncSession) -> ReviewCard:
            item = ReviewItem(
                kind=kind,
                confidence=confidence,
                payload=payload,
                status=STATUS_PENDING,
            )
            session.add(item)
            await session.flush()
            return _card(item)

        return await self.db.write(write)

    async def propose_merge(
        self,
        *,
        from_name: str,
        to_name: str,
        confidence: float,
        reason: str | None = None,
        relation: str = "same_as",
        from_kind: str = "topic",
        to_kind: str = "topic",
    ) -> ReviewCard:
        """Create nodes (if needed) plus a *pending* edge and a review item.

        The edge is not committed here — that requires ``decide(..., "approve")``.
        """

        async def write(session: AsyncSession) -> ReviewCard:
            src = await _get_or_create_node(session, from_name.strip(), from_kind)
            dst = await _get_or_create_node(session, to_name.strip(), to_kind)
            edge = await _pending_edge(
                session,
                from_id=src.id,
                to_id=dst.id,
                relation=relation,
                confidence=confidence,
            )
            item = ReviewItem(
                kind=KIND_MERGE,
                confidence=confidence,
                payload={
                    "from_name": src.canonical_name,
                    "to_name": dst.canonical_name,
                    "from_node_id": src.id,
                    "to_node_id": dst.id,
                    "edge_id": edge.id,
                    "relation": relation,
                    "reason": reason,
                },
                status=STATUS_PENDING,
            )
            session.add(item)
            await session.flush()
            return _card(item)

        return await self.db.write(write)

    async def propose_error_match(
        self,
        *,
        new_title: str,
        past_title: str,
        confidence: float,
        new_capture_id: int | None = None,
        past_capture_id: int | None = None,
        reason: str | None = None,
    ) -> ReviewCard:
        """Queue HITL before treating a past IDE error as the same root cause (#68)."""
        return await self.enqueue(
            kind=KIND_ERROR_MATCH,
            confidence=confidence,
            payload={
                "new_title": new_title,
                "past_title": past_title,
                "new_capture_id": new_capture_id,
                "past_capture_id": past_capture_id,
                "reason": reason,
                "confirmed": False,
            },
        )

    async def propose_ide_batch(
        self,
        *,
        title: str,
        capture_ids: list[int],
        confidence: float = 0.5,
        reason: str | None = None,
    ) -> ReviewCard:
        """Queue HITL for sensitive or bulk IDE chat sync batches (#68)."""
        return await self.enqueue(
            kind=KIND_IDE_BATCH,
            confidence=confidence,
            payload={
                "title": title,
                "capture_ids": list(capture_ids),
                "reason": reason,
                "confirmed": False,
            },
        )

    async def propose_mobile_batch(
        self,
        *,
        title: str,
        capture_ids: list[int],
        confidence: float = 0.4,
        reason: str | None = None,
    ) -> ReviewCard:
        """Queue HITL for phone forwards/voice (#92)."""
        return await self.enqueue(
            kind=KIND_MOBILE_BATCH,
            confidence=confidence,
            payload={
                "title": title,
                "capture_ids": list(capture_ids),
                "reason": reason,
                "confirmed": False,
            },
        )

    async def propose_draft(
        self,
        *,
        draft_kind: str,
        title: str,
        body: str,
        source_capture_ids: list[int] | None = None,
        generator: str = "template",
        extra: dict[str, Any] | None = None,
        confidence: float = 0.5,
        reason: str | None = None,
    ) -> ReviewCard:
        """Queue an auto-generated artifact. Approve confirms; never publishes (#106/#107)."""
        from juno.drafts.kinds import (
            GENERATOR_TEMPLATE,
            PUBLISHED_NO,
            STATUS_PENDING,
            require_draft_kind,
        )

        kind = require_draft_kind(draft_kind)
        gen = generator if generator == GENERATOR_TEMPLATE else GENERATOR_TEMPLATE
        ids = list(source_capture_ids or [])

        async def write(session: AsyncSession) -> ReviewCard:
            item = ReviewItem(
                kind=KIND_DRAFT,
                confidence=confidence,
                payload={
                    "draft_kind": kind,
                    "title": title,
                    "body": body,
                    "source_capture_ids": ids,
                    "generator": gen,
                    "reason": reason,
                    "confirmed": False,
                    "published": False,
                    "discarded": False,
                    "extra": extra or {},
                },
                status=STATUS_PENDING,
            )
            session.add(item)
            await session.flush()
            artifact = DraftArtifact(
                kind=kind,
                title=title,
                body=body,
                extra_json=extra,
                generator=gen,
                status=STATUS_PENDING,
                published=PUBLISHED_NO,
                review_item_id=item.id,
                source_capture_ids=ids,
            )
            session.add(artifact)
            await session.flush()
            payload = dict(item.payload or {})
            payload["artifact_id"] = artifact.id
            item.payload = payload
            await session.flush()
            return _card(item)

        return await self.db.write(write)

    async def next_open(self) -> ReviewCard | None:
        async def load(session: AsyncSession) -> ReviewCard | None:
            row = await _next_row(session)
            return _card(row) if row is not None else None

        return await self.db.read(load)

    async def get(self, item_id: int) -> ReviewCard | None:
        async def load(session: AsyncSession) -> ReviewCard | None:
            row = await session.get(ReviewItem, item_id)
            return _card(row) if row is not None else None

        return await self.db.read(load)

    async def decide(self, item_id: int, decision: Decision) -> DecideResult:
        if decision not in _ALLOWED_DECISIONS:
            raise ValueError(f"unknown decision: {decision}")

        async def write(session: AsyncSession) -> DecideResult:
            row = await session.get(ReviewItem, item_id)
            if row is None:
                raise LookupError(f"review item {item_id} not found")

            already = row.status == STATUS_DECIDED
            applied = False
            if not already:
                if decision == "skip":
                    row.status = STATUS_SKIPPED
                    row.decision = None
                    row.decided_at = None
                else:
                    row.status = STATUS_DECIDED
                    row.decision = decision
                    row.decided_at = datetime.now(UTC)
                    if decision == "approve":
                        applied = await _apply(session, row)
                    else:
                        await _reject(session, row)

            card = _card(row)
            nxt = await _next_row(session, exclude_id=row.id)
            if nxt is not None:
                next_card = _card(nxt)
            elif row.status != STATUS_DECIDED:
                next_card = card
            else:
                next_card = None
            return DecideResult(
                card=card,
                applied=applied,
                already_decided=already,
                next_card=next_card,
            )

        return await self.db.write(write)


def _card(row: ReviewItem) -> ReviewCard:
    payload = row.payload if isinstance(row.payload, dict) else {}
    return ReviewCard(
        id=row.id,
        kind=row.kind,
        confidence=row.confidence,
        payload=dict(payload),
        status=row.status,
        decision=row.decision,
    )


async def _next_row(
    session: AsyncSession,
    *,
    exclude_id: int | None = None,
) -> ReviewItem | None:
    priority = case((ReviewItem.status == STATUS_PENDING, 0), else_=1)
    stmt = (
        select(ReviewItem)
        .where(ReviewItem.status.in_((STATUS_PENDING, STATUS_SKIPPED)))
        .order_by(priority, ReviewItem.created_at, ReviewItem.id)
    )
    if exclude_id is not None:
        stmt = stmt.where(ReviewItem.id != exclude_id)
    result = await session.execute(stmt.limit(1))
    return result.scalar_one_or_none()


async def _get_or_create_node(session: AsyncSession, name: str, kind: str) -> Node:
    result = await session.execute(select(Node).where(Node.canonical_name == name))
    node = result.scalar_one_or_none()
    if node is not None:
        return node
    node = Node(canonical_name=name, kind=kind, status="committed")
    session.add(node)
    await session.flush()
    return node


async def _pending_edge(
    session: AsyncSession,
    *,
    from_id: int,
    to_id: int,
    relation: str,
    confidence: float,
) -> Edge:
    result = await session.execute(
        select(Edge).where(
            Edge.from_id == from_id,
            Edge.to_id == to_id,
            Edge.relation == relation,
            Edge.status != EDGE_REJECTED,
        )
    )
    existing = result.scalar_one_or_none()
    if existing is not None:
        if existing.status != EDGE_COMMITTED:
            existing.status = EDGE_PENDING
            existing.confidence = confidence
        return existing
    edge = Edge(
        from_id=from_id,
        to_id=to_id,
        relation=relation,
        confidence=confidence,
        status=EDGE_PENDING,
    )
    session.add(edge)
    await session.flush()
    return edge


async def _apply(session: AsyncSession, row: ReviewItem) -> bool:
    if row.kind in {KIND_ERROR_MATCH, KIND_IDE_BATCH}:
        payload = dict(row.payload or {})
        payload["confirmed"] = True
        row.payload = payload
        return True
    if row.kind == KIND_DRAFT:
        payload = dict(row.payload or {})
        payload["confirmed"] = True
        payload["discarded"] = False
        payload["published"] = False
        row.payload = payload
        await _set_draft_artifact(session, payload, confirmed=True)
        return True
    if row.kind != KIND_MERGE:
        return False
    edge_id = (row.payload or {}).get("edge_id")
    if edge_id is None:
        return False
    edge = await session.get(Edge, int(edge_id))
    if edge is None:
        return False
    edge.status = EDGE_COMMITTED
    return True


async def _reject(session: AsyncSession, row: ReviewItem) -> None:
    if row.kind in {KIND_ERROR_MATCH, KIND_IDE_BATCH}:
        payload = dict(row.payload or {})
        payload["confirmed"] = False
        row.payload = payload
        return
    if row.kind == KIND_DRAFT:
        payload = dict(row.payload or {})
        payload["confirmed"] = False
        payload["discarded"] = True
        payload["published"] = False
        row.payload = payload
        await _set_draft_artifact(session, payload, confirmed=False)
        return
    if row.kind != KIND_MERGE:
        return
    edge_id = (row.payload or {}).get("edge_id")
    if edge_id is None:
        return
    edge = await session.get(Edge, int(edge_id))
    if edge is not None and edge.status != EDGE_COMMITTED:
        edge.status = EDGE_REJECTED


async def _set_draft_artifact(
    session: AsyncSession, payload: dict[str, Any], *, confirmed: bool
) -> None:
    from juno.drafts.kinds import PUBLISHED_NO, STATUS_CONFIRMED, STATUS_DISCARDED

    artifact_id = payload.get("artifact_id")
    if artifact_id is None:
        return
    artifact = await session.get(DraftArtifact, int(artifact_id))
    if artifact is None:
        return
    artifact.status = STATUS_CONFIRMED if confirmed else STATUS_DISCARDED
    artifact.published = PUBLISHED_NO
    if confirmed:
        from juno.drafts.flashcards import activate_approved_flashcard

        await activate_approved_flashcard(session, artifact)
