from __future__ import annotations

import json

import pytest
from sqlalchemy import func, select

from juno.graph.db import Database
from juno.graph.ownership import (
    EXPORT_FORMAT,
    WIPE_CONFIRM_PHRASE,
    build_export_payload,
    wipe_local_data,
    write_export_file,
)
from juno.graph.vectors import VectorStore
from juno.hitl.queue import ReviewQueue
from juno.ingest.pipeline import IngestPipeline
from juno.llm.embedder import StubEmbedder
from juno.models import Capture


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


@pytest.mark.asyncio
async def test_export_includes_graph_and_vectors(settings, db, vectors, pipeline):
    await pipeline.ingest_text("export marker beta-99", source_type="upload", title="note")
    review = ReviewQueue(db)
    await review.propose_merge(from_name="Alpha", to_name="Beta", confidence=0.4)

    payload = await build_export_payload(
        settings,
        db=db,
        vectors=vectors,
        embedder=StubEmbedder(),
    )
    assert payload["format"] == EXPORT_FORMAT
    assert payload["version"] == 1
    assert len(payload["graph"]["captures"]) == 1
    assert len(payload["graph"]["chunks"]) == 1
    assert len(payload["graph"]["review_items"]) == 1
    assert payload["vectors"] is not None
    assert payload["vectors"]["count"] == 1
    assert "beta-99" in payload["vectors"]["documents"][0]
    assert payload["vectors"]["embeddings"]


@pytest.mark.asyncio
async def test_write_export_file_roundtrip(tmp_path, settings, db):
    payload = await build_export_payload(
        settings,
        db=db,
        vectors=None,
        embedder=StubEmbedder(),
    )
    path = write_export_file(payload, tmp_path / "bundle.json")
    loaded = json.loads(path.read_text(encoding="utf-8"))
    assert loaded["format"] == EXPORT_FORMAT
    assert "graph" in loaded


@pytest.mark.asyncio
async def test_wipe_requires_exact_confirm(settings, db, pipeline):
    await pipeline.ingest_text("keep until wipe")
    with pytest.raises(ValueError, match=WIPE_CONFIRM_PHRASE):
        await wipe_local_data(settings, confirm="delete-everything")
    await db.dispose()


@pytest.mark.asyncio
async def test_wipe_clears_sqlite_graph_and_recreates_schema(settings, db):
    pipeline = IngestPipeline(db)
    await pipeline.ingest_text("will be wiped", title="temp")
    await db.dispose()

    removed = await wipe_local_data(settings, confirm=WIPE_CONFIRM_PHRASE)
    assert any(settings.sqlite_path.name in path for path in removed)
    assert settings.sqlite_path.is_file()

    fresh = Database(settings)

    async def capture_count(session):
        return int((await session.execute(select(func.count()).select_from(Capture))).scalar_one())

    assert await fresh.read(capture_count) == 0
    await fresh.dispose()


@pytest.mark.asyncio
async def test_wipe_removes_chroma_directory_when_not_open(settings, db):
    """Avoid opening PersistentClient in-process before wipe (Windows file locks)."""
    chroma = settings.chroma_path
    chroma.mkdir(parents=True, exist_ok=True)
    marker = chroma / "stale-export.txt"
    marker.write_text("leftover", encoding="utf-8")
    await db.dispose()

    removed = await wipe_local_data(settings, confirm=WIPE_CONFIRM_PHRASE)
    assert chroma.is_dir()
    assert not marker.exists()
    assert any("chroma" in path for path in removed)
    assert VectorStore(settings, StubEmbedder()).count() == 0
