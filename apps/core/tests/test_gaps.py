from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from juno.graph.db import Database
from juno.hitl.queue import KIND_SKILL_GAP, ReviewQueue
from juno.models import Capture
from juno.rag.gaps import apply_skill_gaps, find_skill_gaps


@pytest.fixture
async def db(settings):
    database = Database(settings)
    await database.migrate()
    yield database
    await database.dispose()


async def _add(
    db: Database,
    *,
    source: str,
    title: str,
    kind: str | None = None,
    uri: str | None = None,
    captured_at: datetime | None = None,
) -> Capture:
    async def write(session):
        raw = {"kind": kind} if kind else {}
        row = Capture(
            source_type=source,
            title=title,
            text=title,
            uri=uri,
            raw_json=raw or None,
            status="committed",
            captured_at=captured_at or datetime.now(UTC),
        )
        session.add(row)
        await session.flush()
        return row

    return await db.write(write)


@pytest.mark.asyncio
async def test_unfinished_read_queues_hitl_once(db):
    old = datetime.now(UTC) - timedelta(days=5)
    await _add(
        db,
        source="browser",
        title="Deep dive into ownership",
        uri="https://example.test/own",
        captured_at=old,
    )
    gaps = await find_skill_gaps(db, now=datetime.now(UTC))
    unfinished = [g for g in gaps if g.kind == "unfinished_read"]
    assert unfinished
    first = await apply_skill_gaps(db, gaps, paused=False)
    assert first.queued >= 1
    nxt = await ReviewQueue(db).next_open()
    assert nxt is not None
    assert nxt.kind == KIND_SKILL_GAP
    assert "will not nag" in nxt.summary()
    second = await apply_skill_gaps(db, gaps, paused=False)
    assert second.queued == 0
    assert second.listed == 0


@pytest.mark.asyncio
async def test_pause_skips_gap_apply(db):
    old = datetime.now(UTC) - timedelta(days=5)
    await _add(
        db,
        source="browser",
        title="Unfinished article",
        uri="https://example.test/unread",
        captured_at=old,
    )
    gaps = await find_skill_gaps(db)
    skipped = await apply_skill_gaps(db, gaps, paused=True)
    assert skipped.queued == 0
    assert await ReviewQueue(db).next_open() is None
