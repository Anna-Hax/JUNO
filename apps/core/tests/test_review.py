from __future__ import annotations

import pytest
from sqlalchemy import func, select

from juno.graph.db import Database
from juno.hitl.queue import EDGE_COMMITTED, EDGE_PENDING, EDGE_REJECTED, ReviewQueue
from juno.models import Edge


@pytest.fixture
async def queue(settings):
    db = Database(settings)
    await db.migrate()
    q = ReviewQueue(db)
    yield q
    await db.dispose()


async def _edge_status(db: Database, edge_id: int) -> str | None:
    async def load(session):
        edge = await session.get(Edge, edge_id)
        return None if edge is None else edge.status

    return await db.read(load)


async def _committed_edge_count(db: Database) -> int:
    async def load(session):
        result = await session.execute(
            select(func.count()).select_from(Edge).where(Edge.status == EDGE_COMMITTED)
        )
        return int(result.scalar_one())

    return await db.read(load)


@pytest.mark.asyncio
async def test_propose_merge_stays_pending_until_approve(queue):
    card = await queue.propose_merge(
        from_name="Rust ownership",
        to_name="Rust",
        confidence=0.41,
        reason="same topic cluster",
    )
    assert card.kind == "merge"
    assert card.status == "pending"
    assert card.decision is None
    edge_id = int(card.payload["edge_id"])
    assert await _edge_status(queue.db, edge_id) == EDGE_PENDING
    assert await _committed_edge_count(queue.db) == 0

    result = await queue.decide(card.id, "approve")
    assert result.already_decided is False
    assert result.applied is True
    assert result.card.status == "decided"
    assert result.card.decision == "approve"
    assert await _edge_status(queue.db, edge_id) == EDGE_COMMITTED
    assert await _committed_edge_count(queue.db) == 1


@pytest.mark.asyncio
async def test_reject_does_not_commit_merge(queue):
    card = await queue.propose_merge(from_name="Alpha", to_name="Beta", confidence=0.2)
    edge_id = int(card.payload["edge_id"])

    result = await queue.decide(card.id, "reject")
    assert result.applied is False
    assert result.card.decision == "reject"
    assert await _edge_status(queue.db, edge_id) == EDGE_REJECTED
    assert await _committed_edge_count(queue.db) == 0


@pytest.mark.asyncio
async def test_skip_leaves_merge_pending(queue):
    card = await queue.propose_merge(from_name="One", to_name="Two", confidence=0.5)
    edge_id = int(card.payload["edge_id"])

    result = await queue.decide(card.id, "skip")
    assert result.applied is False
    assert result.already_decided is False
    assert result.card.status == "skipped"
    assert result.card.decision is None
    assert await _edge_status(queue.db, edge_id) == EDGE_PENDING
    assert await _committed_edge_count(queue.db) == 0

    later = await queue.decide(card.id, "approve")
    assert later.applied is True
    assert await _edge_status(queue.db, edge_id) == EDGE_COMMITTED


@pytest.mark.asyncio
async def test_approve_is_idempotent(queue):
    card = await queue.propose_merge(from_name="A", to_name="B", confidence=0.9)
    first = await queue.decide(card.id, "approve")
    second = await queue.decide(card.id, "reject")
    assert first.applied is True
    assert second.already_decided is True
    assert second.applied is False
    assert second.card.decision == "approve"
    assert await _committed_edge_count(queue.db) == 1


@pytest.mark.asyncio
async def test_next_open_prefers_pending_then_skipped(queue):
    first = await queue.propose_merge(from_name="a", to_name="b", confidence=0.1)
    second = await queue.propose_merge(from_name="c", to_name="d", confidence=0.2)
    await queue.decide(first.id, "skip")

    nxt = await queue.next_open()
    assert nxt is not None
    assert nxt.id == second.id

    await queue.decide(second.id, "reject")
    leftover = await queue.next_open()
    assert leftover is not None
    assert leftover.id == first.id
    assert leftover.status == "skipped"


@pytest.mark.asyncio
async def test_decide_missing_item(queue):
    with pytest.raises(LookupError):
        await queue.decide(999, "approve")


@pytest.mark.asyncio
async def test_generic_enqueue_has_no_graph_side_effect(queue):
    card = await queue.enqueue(kind="ingest_batch", payload={"batch": "mobile"}, confidence=0.3)
    result = await queue.decide(card.id, "approve")
    assert result.applied is False
    assert await _committed_edge_count(queue.db) == 0


@pytest.mark.asyncio
async def test_error_match_stays_unconfirmed_until_approve(queue):
    card = await queue.propose_error_match(
        new_title="database is locked",
        past_title="sqlite lock on ingest",
        confidence=0.82,
        new_capture_id=10,
        past_capture_id=3,
        reason="similar stack only until you confirm",
    )
    assert card.kind == "error_match"
    assert card.status == "pending"
    assert card.payload.get("confirmed") is False
    assert "same root cause" in card.summary()

    rejected = await queue.decide(card.id, "reject")
    assert rejected.applied is False
    assert rejected.card.payload.get("confirmed") is False

    other = await queue.propose_error_match(
        new_title="WAL busy",
        past_title="database is locked",
        confidence=0.9,
        new_capture_id=11,
        past_capture_id=10,
    )
    approved = await queue.decide(other.id, "approve")
    assert approved.applied is True
    assert approved.card.payload.get("confirmed") is True


@pytest.mark.asyncio
async def test_ide_batch_review_confirms_on_approve(queue):
    card = await queue.propose_ide_batch(
        title="Cursor chats 2026-09-02",
        capture_ids=[1, 2, 3],
        reason="bulk sync of composer sessions",
    )
    assert card.kind == "ide_batch"
    assert "bulk IDE sync" in card.summary()
    result = await queue.decide(card.id, "approve")
    assert result.applied is True
    assert result.card.payload.get("confirmed") is True
    assert result.card.payload.get("capture_ids") == [1, 2, 3]
