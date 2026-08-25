from __future__ import annotations

import asyncio

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import OperationalError

from juno.graph.db import Database
from juno.ingest.pipeline import IngestPipeline
from juno.models import Capture, Chunk


@pytest.fixture
async def db(settings):
    database = Database(settings)
    await database.migrate()
    yield database
    await database.dispose()


@pytest.mark.asyncio
async def test_sqlite_uses_wal(db):
    assert (await db.journal_mode()).lower() == "wal"

    async def busy(session):
        return int((await session.execute(text("PRAGMA busy_timeout"))).scalar_one())

    assert await db.read(busy) >= 5000


@pytest.mark.asyncio
async def test_concurrent_ingest_does_not_lock(db):
    pipeline = IngestPipeline(db)
    n = 24
    try:
        results = await asyncio.gather(
            *[
                pipeline.ingest_text(
                    f"concurrent note {i} rust ownership borrowing",
                    source_type="upload",
                    title=f"note-{i}",
                )
                for i in range(n)
            ]
        )
    except OperationalError as exc:
        pytest.fail(f"SQLite locked under concurrent ingest: {exc}")

    assert all(item.status == "committed" for item in results)
    ids = [item.capture_id for item in results]
    assert None not in ids
    assert len(set(ids)) == n

    async def counts(session):
        captures = int(
            (await session.execute(select(func.count()).select_from(Capture))).scalar_one()
        )
        chunks = int((await session.execute(select(func.count()).select_from(Chunk))).scalar_one())
        return captures, chunks

    captures, chunks = await db.read(counts)
    assert captures == n
    assert chunks == n


@pytest.mark.asyncio
async def test_reads_proceed_during_serialized_writes(db):
    started = asyncio.Event()
    release = asyncio.Event()

    async def slow_write(session):
        session.add(Capture(source_type="upload", text="held", status="committed"))
        started.set()
        await release.wait()

    async def count(session):
        return int((await session.execute(select(func.count()).select_from(Capture))).scalar_one())

    writer = asyncio.create_task(db.write(slow_write))
    await started.wait()
    seen = await db.read(count)
    release.set()
    await writer
    after = await db.read(count)
    assert seen == 0
    assert after == 1
