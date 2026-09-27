"""Keyword fusion, salience, topic drafts, traces, and source warnings."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select

from juno.drafts.consolidate import queue_topic_summary
from juno.drafts.kinds import DRAFT_KIND_TOPIC
from juno.graph.db import Database
from juno.graph.vectors import VectorStore
from juno.ingest.pipeline import IngestPipeline
from juno.jobs.health import record_named_health
from juno.llm.embedder import StubEmbedder
from juno.models import Capture, DraftArtifact
from juno.rag.health import (
    EMPTY_EXTENSION_WARNING,
    STUB_FALLBACK_WARNING,
    status_warnings,
    warning_lines,
)
from juno.rag.lexical import bm25_rank, reciprocal_rank_fusion
from juno.rag.salience import salience_score
from juno.rag.trace import record_search_trace


def test_bm25_prefers_the_document_that_contains_the_token():
    docs = [
        ("garden", "tomatoes soil and watering"),
        ("rust", "ownership rust-ownership-xyz single owner"),
    ]
    ranked = bm25_rank("rust-ownership-xyz", docs, limit=2)
    assert ranked[0] == "rust"


def test_rrf_keeps_a_keyword_hit_the_vector_list_ranked_second():
    fused = reciprocal_rank_fusion(
        [
            ["garden", "rust"],
            ["rust"],
        ]
    )
    assert fused[0] == "rust"


def test_salience_keeps_a_strong_older_match_above_the_push_floor():
    now = datetime.now(UTC)
    score = salience_score(
        0.95,
        now - timedelta(days=10),
        now,
        text="Ownership in Rust means each value has a single owner and a long note.",
    )
    assert score >= 0.55


def test_salience_downranks_a_thin_note():
    now = datetime.now(UTC)
    thin = salience_score(0.6, now - timedelta(days=40), now, text="short")
    solid = salience_score(
        0.6,
        now - timedelta(days=40),
        now,
        text="A substantial note about the same topic with enough text to matter.",
        has_highlights=True,
    )
    assert thin < solid


def test_warning_lines_skip_an_intentional_stub():
    now = datetime.now(UTC)
    assert warning_lines(
        embedding_fallback=False,
        extension_last_success=now,
        captures_in_window=0,
        now=now,
    ) == [EMPTY_EXTENSION_WARNING]
    assert (
        warning_lines(
            embedding_fallback=False,
            extension_last_success=None,
            captures_in_window=0,
            now=now,
        )
        == []
    )


def test_warning_lines_include_embedder_fallback():
    now = datetime.now(UTC)
    lines = warning_lines(
        embedding_fallback=True,
        extension_last_success=None,
        captures_in_window=3,
        now=now,
    )
    assert lines == [STUB_FALLBACK_WARNING]


@pytest.fixture
async def db(settings):
    database = Database(settings)
    await database.migrate()
    yield database
    await database.dispose()


@pytest.mark.asyncio
async def test_keyword_token_outranks_an_unrelated_dense_neighbor(settings, db):
    vectors = VectorStore(settings, StubEmbedder())
    pipeline = IngestPipeline(db, vectors=vectors)
    await pipeline.ingest_text(
        "Unrelated gardening notes about tomatoes and soil pH.",
        source_type="upload",
        title="Garden",
    )
    rust = await pipeline.ingest_text(
        "Ownership in Rust means each value has a single owner rust-ownership-xyz.",
        source_type="upload",
        title="Rust notes",
    )
    from juno.rag.engine import retrieve

    hits = await retrieve("rust-ownership-xyz", vectors=vectors, db=db, n_results=2)
    assert hits
    assert hits[0].capture_id == rust.capture_id


@pytest.mark.asyncio
async def test_topic_summary_queues_once(settings, db):
    async def add(session):
        now = datetime.now(UTC)
        session.add(
            Capture(
                source_type="upload",
                title="Rust ownership",
                text="notes about rust ownership",
                status="committed",
                captured_at=now,
            )
        )
        session.add(
            Capture(
                source_type="upload",
                title="Vector indexes",
                text="notes about vector indexes",
                status="committed",
                captured_at=now,
            )
        )

    await db.write(add)
    first = await queue_topic_summary(db)
    assert first is not None
    second = await queue_topic_summary(db)
    assert second is None

    async def load(session):
        result = await session.execute(
            select(DraftArtifact).where(DraftArtifact.kind == DRAFT_KIND_TOPIC)
        )
        return list(result.scalars())

    rows = await db.read(load)
    assert len(rows) == 1
    assert rows[0].status == "pending"
    assert rows[0].published == "false"


@pytest.mark.asyncio
async def test_search_writes_a_trace_line(settings, db):
    vectors = VectorStore(settings, StubEmbedder())
    pipeline = IngestPipeline(db, vectors=vectors)
    await pipeline.ingest_text(
        "Ownership in Rust means each value has a single owner.",
        source_type="upload",
        title="Rust",
    )
    from juno.rag.engine import search

    trace_dir = settings.juno_data_dir / "traces"
    await search(
        "rust ownership",
        vectors=vectors,
        db=db,
        n_results=3,
        mode="retrieve",
        trace_dir=trace_dir,
    )
    files = list(trace_dir.glob("*.jsonl"))
    assert len(files) == 1
    record = json.loads(files[0].read_text(encoding="utf-8").splitlines()[0])
    assert record["mode"] == "retrieve"
    assert record["llm_used"] is False
    assert record["cites_valid"] is False
    assert record["hit_ids"]


def test_trace_write_failure_is_swallowed(tmp_path):
    blocked = tmp_path / "not-a-dir"
    blocked.write_text("file", encoding="utf-8")
    record_search_trace(
        blocked / "traces",
        query="q",
        mode="retrieve",
        hits=[],
        llm_used=False,
        cites_valid=False,
    )


@pytest.mark.asyncio
async def test_status_warns_when_extension_heartbeat_has_no_captures(settings, db):
    await record_named_health(db, "extension", detail="synced", ok=True)
    warnings = await status_warnings(db, embedding_fallback=False)
    assert EMPTY_EXTENSION_WARNING in warnings

    async def add(session):
        session.add(
            Capture(
                source_type="browser",
                title="page",
                text="hello page",
                status="committed",
                captured_at=datetime.now(UTC),
            )
        )

    await db.write(add)
    quiet = await status_warnings(db, embedding_fallback=False)
    assert EMPTY_EXTENSION_WARNING not in quiet


@pytest.mark.asyncio
async def test_topic_summary_does_not_add_a_capture(settings, db):
    async def add(session):
        now = datetime.now(UTC)
        session.add(
            Capture(
                source_type="browser",
                title="one",
                text="body one",
                status="committed",
                captured_at=now,
            )
        )
        session.add(
            Capture(
                source_type="browser",
                title="two",
                text="body two",
                status="committed",
                captured_at=now,
            )
        )

    await db.write(add)

    async def count(session):
        result = await session.execute(select(func.count()).select_from(Capture))
        return int(result.scalar_one())

    before = await db.read(count)
    await queue_topic_summary(db)
    after = await db.read(count)
    assert after == before
