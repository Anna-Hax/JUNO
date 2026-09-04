from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from juno.graph.db import Database
from juno.graph.ownership import WIPE_CONFIRM_PHRASE
from juno.graph.prune import (
    PRUNE_CONFIRM_PHRASE,
    STATUS_ARCHIVED,
    list_prune_candidates,
    propose_prune,
)
from juno.graph.vectors import VectorStore
from juno.hitl.queue import KIND_PRUNE, ReviewQueue
from juno.ingest.pipeline import IngestPipeline
from juno.llm.embedder import StubEmbedder
from juno.models import Capture
from juno.rag.engine import retrieve


@pytest.fixture
async def db(settings):
    database = Database(settings)
    await database.migrate()
    yield database
    await database.dispose()


@pytest.fixture
def vectors(settings):
    return VectorStore(settings, StubEmbedder())


@pytest.fixture
def pipeline(db, vectors):
    return IngestPipeline(db, vectors=vectors)


async def _set_captured_at(db: Database, capture_id: int, *, days_ago: int) -> None:
    when = datetime.now(UTC) - timedelta(days=days_ago)

    async def write(session: AsyncSession) -> None:
        cap = await session.get(Capture, capture_id)
        assert cap is not None
        cap.captured_at = when

    await db.write(write)


async def _status(db: Database, capture_id: int) -> str | None:
    async def load(session: AsyncSession) -> str | None:
        cap = await session.get(Capture, capture_id)
        return None if cap is None else cap.status

    return await db.read(load)


async def _insert_failed(db: Database) -> int:
    async def write(session: AsyncSession) -> int:
        cap = Capture(
            source_type="upload",
            title="bad pdf",
            text="",
            status="failed",
            error_reason="unreadable",
        )
        session.add(cap)
        await session.flush()
        return cap.id

    return await db.write(write)


def test_prune_confirm_is_not_wipe():
    assert PRUNE_CONFIRM_PHRASE == "prune-selected"
    assert PRUNE_CONFIRM_PHRASE != WIPE_CONFIRM_PHRASE


@pytest.mark.asyncio
async def test_candidates_are_old_unused_or_failed_not_highlighted(db, pipeline):
    old = await pipeline.ingest_text("short unused note", source_type="upload", title="dust")
    keep_hl = await pipeline.ingest_text("also short", source_type="upload", title="quoted")
    fresh = await pipeline.ingest_text("fresh unused", source_type="upload", title="today")
    failed_id = await _insert_failed(db)

    async def mark_highlights(session: AsyncSession) -> None:
        cap = await session.get(Capture, keep_hl.capture_id)
        assert cap is not None
        cap.raw_json = {"highlights": ["keep this"]}

    await db.write(mark_highlights)
    await _set_captured_at(db, old.capture_id, days_ago=100)
    await _set_captured_at(db, keep_hl.capture_id, days_ago=100)
    await _set_captured_at(db, failed_id, days_ago=10)

    found = await list_prune_candidates(db, min_age_days=90)
    ids = {c.id for c in found}
    assert old.capture_id in ids
    assert failed_id in ids
    assert keep_hl.capture_id not in ids
    assert fresh.capture_id not in ids


@pytest.mark.asyncio
async def test_approve_archives_and_drops_vectors_reject_does_not(db, vectors, pipeline):
    old = await pipeline.ingest_text("prune me please", source_type="upload", title="stale")
    await _set_captured_at(db, old.capture_id, days_ago=120)
    assert vectors.count() >= 1
    before = vectors.count()

    candidates = await list_prune_candidates(db, min_age_days=90)
    card = await propose_prune(db, candidates=candidates)
    assert card is not None
    assert card.kind == KIND_PRUNE
    assert card.status == "pending"
    assert await _status(db, old.capture_id) == "committed"

    rejected = await ReviewQueue(db, vectors=vectors).decide(card.id, "reject")
    assert rejected.applied is False
    assert await _status(db, old.capture_id) == "committed"
    assert vectors.count() == before

    again = await propose_prune(db, candidates=candidates)
    assert again is not None
    approved = await ReviewQueue(db, vectors=vectors).decide(again.id, "approve")
    assert approved.applied is True
    assert approved.card.payload.get("archived") is True
    assert await _status(db, old.capture_id) == STATUS_ARCHIVED
    hits = await retrieve("prune me please", vectors=vectors, db=db)
    assert hits == []
    assert vectors.count() == 0


@pytest.mark.asyncio
async def test_duplicate_pending_prune_is_not_requeued(db, pipeline):
    old = await pipeline.ingest_text("dup prune", source_type="upload", title="dup")
    await _set_captured_at(db, old.capture_id, days_ago=100)
    candidates = await list_prune_candidates(db, min_age_days=90)
    first = await propose_prune(db, candidates=candidates)
    second = await propose_prune(db, candidates=candidates)
    assert first is not None
    assert second is None
