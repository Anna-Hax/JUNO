from __future__ import annotations

import pytest

from juno.graph.db import Database
from juno.hitl.queue import EDGE_COMMITTED, EDGE_PENDING, ReviewQueue
from juno.hitl.trust import get_dial, set_auto, should_auto_commit
from juno.models import Edge


@pytest.fixture
async def db(settings):
    database = Database(settings)
    await database.migrate()
    yield database
    await database.dispose()


@pytest.mark.asyncio
async def test_mobile_and_drafts_stay_gated(db):
    with pytest.raises(ValueError, match="gated"):
        await set_auto(db, "mobile", True)
    with pytest.raises(ValueError, match="gated"):
        await set_auto(db, "drafts", True)
    assert await should_auto_commit(db, "mobile", 0.99) is False
    assert await should_auto_commit(db, "drafts", 0.99) is False


@pytest.mark.asyncio
async def test_merge_auto_commit_after_enough_approvals(db):
    queue = ReviewQueue(db)
    assert await should_auto_commit(db, "merge", 0.95) is False
    for i in range(5):
        card = await queue.propose_merge(from_name=f"A{i}", to_name=f"B{i}", confidence=0.4)
        await queue.decide(card.id, "approve")
    dial = await get_dial(db, "merge")
    assert dial.successes == 5
    assert dial.auto is True
    assert await should_auto_commit(db, "merge", 0.95) is True
    assert await should_auto_commit(db, "merge", 0.5) is False

    auto = await queue.propose_merge(from_name="Rust", to_name="Ownership", confidence=0.9)
    assert auto.status == "decided"
    assert auto.payload.get("auto_committed") is True
    edge_id = int(auto.payload["edge_id"])

    async def load(session):
        edge = await session.get(Edge, edge_id)
        return edge.status if edge else None

    assert await db.read(load) == EDGE_COMMITTED


@pytest.mark.asyncio
async def test_operator_can_turn_merge_auto_off(db):
    queue = ReviewQueue(db)
    for i in range(5):
        card = await queue.propose_merge(from_name=f"x{i}", to_name=f"y{i}", confidence=0.4)
        await queue.decide(card.id, "approve")
    await set_auto(db, "merge", False)
    card = await queue.propose_merge(from_name="Keep", to_name="Pending", confidence=0.99)
    assert card.status == "pending"
    edge_id = int(card.payload["edge_id"])

    async def load(session):
        edge = await session.get(Edge, edge_id)
        return edge.status if edge else None

    assert await db.read(load) == EDGE_PENDING
