from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import select

from juno.bot.cards import cards_cmd, cards_keyboard, parse_srs_callback
from juno.bot.services import BOT_DATA_KEY, BotServices
from juno.drafts.flashcards import (
    extract_highlights,
    next_due_card,
    queue_highlight_flashcards,
    review_card,
)
from juno.graph.db import Database
from juno.hitl.queue import ReviewQueue
from juno.models import Capture, Flashcard


@pytest.fixture
async def db(settings):
    database = Database(settings)
    await database.migrate()
    yield database
    await database.dispose()


async def _add_highlighted(db: Database, *, title: str, quote: str) -> Capture:
    async def write(session):
        row = Capture(
            source_type="browser",
            title=title,
            text=quote,
            raw_json={"highlights": [{"text": quote}]},
            status="committed",
        )
        session.add(row)
        await session.flush()
        return row

    return await db.write(write)


def test_extract_highlights_skips_short():
    cap = Capture(
        id=1,
        source_type="browser",
        title="Page",
        raw_json={"highlights": [{"text": "ab"}, {"text": "A useful quote here"}]},
    )
    found = extract_highlights(cap)
    assert len(found) == 1
    assert found[0].text == "A useful quote here"
    assert found[0].back == "Page"


@pytest.mark.asyncio
async def test_highlights_queue_as_unpublished_drafts(db):
    await _add_highlighted(db, title="Rust book", quote="Ownership moves values")
    queued = await queue_highlight_flashcards(db, paused=False)
    assert len(queued) == 1
    card = queued[0]
    assert card.payload["draft_kind"] == "flashcard"
    assert card.payload["published"] is False
    assert "Ownership moves values" in card.payload["body"]

    again = await queue_highlight_flashcards(db, paused=False)
    assert again == []

    paused = await queue_highlight_flashcards(db, paused=True)
    assert paused == []

    async def count_cards(session):
        result = await session.execute(select(Flashcard))
        return list(result.scalars())

    assert await db.read(count_cards) == []

    approved = await ReviewQueue(db).decide(card.id, "approve")
    assert approved.card.payload["published"] is False
    rows = await db.read(count_cards)
    assert len(rows) == 1
    assert rows[0].front == "Ownership moves values"
    assert rows[0].back == "Rust book"
    assert rows[0].artifact_id == int(approved.card.payload["artifact_id"])


@pytest.mark.asyncio
async def test_srs_again_and_good(db):
    await _add_highlighted(db, title="Topic", quote="Intervals compound with ease")
    queued = await queue_highlight_flashcards(db)
    await ReviewQueue(db).decide(queued[0].id, "approve")
    due = await next_due_card(db)
    assert due is not None
    now = datetime.now(UTC)
    graded = await review_card(db, due.id, "good")
    assert graded.reps == 1
    assert graded.interval_days == 1
    assert graded.due_at > now + timedelta(hours=12)

    later = await review_card(db, graded.id, "again")
    assert later.reps == 0
    assert later.interval_days == 0
    assert later.due_at <= datetime.now(UTC) + timedelta(minutes=11)


def test_parse_srs_callback():
    assert parse_srs_callback("srs:4:again") == (4, "again")
    assert parse_srs_callback("srs:4:good") == (4, "good")
    assert parse_srs_callback("rev:4:approve") is None
    labels = [btn.text for row in cards_keyboard(4).inline_keyboard for btn in row]
    assert labels == ["Again", "Good"]


@pytest.mark.asyncio
async def test_cards_cmd_queues_drafts_and_skips_when_paused(settings, db):
    await _add_highlighted(db, title="Page", quote="Spaced repetition works")
    settings.allowed_telegram_user_ids = "42"
    app = MagicMock()
    app.state.capture_paused = False
    svc = BotServices(settings=settings, db=db, app=app)
    ctx = MagicMock()
    ctx.application.bot_data = {BOT_DATA_KEY: svc, "settings": settings}
    update = MagicMock()
    update.effective_user.id = 42
    update.message.reply_text = AsyncMock()
    await cards_cmd(update, ctx)
    text = update.message.reply_text.await_args.args[0]
    assert "Queued 1 flashcard draft" in text
    assert "No flashcards due" in text

    app.state.capture_paused = True
    update.message.reply_text = AsyncMock()
    await cards_cmd(update, ctx)
    paused_text = update.message.reply_text.await_args.args[0]
    assert "paused" in paused_text.lower()
    assert "Queued" not in paused_text
