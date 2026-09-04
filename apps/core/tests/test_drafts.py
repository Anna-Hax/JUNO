from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from sqlalchemy import func, select

from juno.drafts import (
    DRAFT_KIND_JOURNAL,
    GENERATOR_TEMPLATE,
    enqueue_journal_draft,
    format_journal_snippet,
    maybe_enqueue_smoke_draft,
)
from juno.graph.db import Database
from juno.hitl.queue import KIND_DRAFT, ReviewQueue
from juno.models import Capture


@pytest.fixture
async def db(settings):
    database = Database(settings)
    await database.migrate()
    yield database
    await database.dispose()


async def _add_capture(db: Database, *, title: str, text: str = "body") -> Capture:
    async def write(session):
        row = Capture(
            source_type="upload",
            title=title,
            text=text,
            status="committed",
        )
        session.add(row)
        await session.flush()
        return row

    return await db.write(write)


async def _capture_count(db: Database) -> int:
    async def load(session):
        result = await session.execute(select(func.count()).select_from(Capture))
        return int(result.scalar_one())

    return await db.read(load)


def test_format_journal_snippet_from_titles():
    now = datetime(2026, 9, 5, tzinfo=UTC)
    caps = [
        Capture(id=1, source_type="browser", title="Rust ownership notes", text="a"),
        Capture(id=2, source_type="upload", title="WAL busy", text="b"),
    ]
    text = format_journal_snippet(caps, now=now)
    assert "2026-09-05" in text
    assert "Rust ownership notes [browser]" in text
    assert "WAL busy [upload]" in text
    assert "not a published journal" in text


def test_format_journal_snippet_empty():
    text = format_journal_snippet([], now=datetime(2026, 9, 5, tzinfo=UTC))
    assert "No recent captures" in text
    assert "HITL review only" in text


@pytest.mark.asyncio
async def test_journal_draft_stays_unpublished_after_approve(db):
    cap = await _add_capture(db, title="Cursor HITL notes")
    before = await _capture_count(db)
    card = await enqueue_journal_draft(db, captures=[cap])
    assert card.kind == KIND_DRAFT
    assert card.status == "pending"
    assert card.payload["draft_kind"] == DRAFT_KIND_JOURNAL
    assert card.payload["generator"] == GENERATOR_TEMPLATE
    assert card.payload["published"] is False
    assert card.payload["confirmed"] is False
    assert cap.id in card.payload["source_capture_ids"]
    assert "Cursor HITL notes" in card.payload["body"]
    assert "not published" in card.summary()

    result = await ReviewQueue(db).decide(card.id, "approve")
    assert result.applied is True
    assert result.card.payload["confirmed"] is True
    assert result.card.payload["published"] is False
    assert result.card.payload["discarded"] is False
    assert await _capture_count(db) == before


@pytest.mark.asyncio
async def test_journal_draft_reject_discards_without_publish(db):
    card = await enqueue_journal_draft(db, captures=[])
    result = await ReviewQueue(db).decide(card.id, "reject")
    assert result.applied is False
    assert result.card.payload["confirmed"] is False
    assert result.card.payload["discarded"] is True
    assert result.card.payload["published"] is False
    assert await _capture_count(db) == 0


@pytest.mark.asyncio
async def test_journal_draft_skip_stays_pending(db):
    card = await enqueue_journal_draft(db, captures=[])
    result = await ReviewQueue(db).decide(card.id, "skip")
    assert result.card.status == "skipped"
    assert result.card.payload["published"] is False
    later = await ReviewQueue(db).decide(card.id, "approve")
    assert later.applied is True
    assert later.card.payload["published"] is False


@pytest.mark.asyncio
async def test_llm_generator_setting_still_uses_template(db):
    card = await enqueue_journal_draft(db, captures=[], generator="llm")
    assert card.payload["generator"] == GENERATOR_TEMPLATE


@pytest.mark.asyncio
async def test_smoke_enqueues_when_enabled(settings, db):
    settings.juno_drafts_smoke = True
    app = SimpleNamespace(state=SimpleNamespace(settings=settings, db=db, capture_paused=False))
    card = await maybe_enqueue_smoke_draft(app)
    assert card is not None
    assert card.kind == KIND_DRAFT
    assert card.status == "pending"


@pytest.mark.asyncio
async def test_smoke_skips_when_paused_or_off(settings, db):
    settings.juno_drafts_smoke = True
    paused = SimpleNamespace(state=SimpleNamespace(settings=settings, db=db, capture_paused=True))
    assert await maybe_enqueue_smoke_draft(paused) is None

    settings.juno_drafts_smoke = False
    off = SimpleNamespace(state=SimpleNamespace(settings=settings, db=db, capture_paused=False))
    assert await maybe_enqueue_smoke_draft(off) is None
