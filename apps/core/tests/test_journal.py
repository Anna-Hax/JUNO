from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from juno.bot.handlers import drafts_cmd
from juno.bot.services import BOT_DATA_KEY, BotServices
from juno.drafts.journal import queue_ide_journal_draft, queue_ide_readme_draft
from juno.graph.db import Database
from juno.hitl.queue import ReviewQueue
from juno.models import Capture, DraftArtifact


@pytest.fixture
async def db(settings):
    database = Database(settings)
    await database.migrate()
    yield database
    await database.dispose()


async def _add(db: Database, *, source: str, title: str, text: str = "body") -> Capture:
    async def write(session):
        row = Capture(source_type=source, title=title, text=text, status="committed")
        session.add(row)
        await session.flush()
        return row

    return await db.write(write)


@pytest.mark.asyncio
async def test_ide_journal_ignores_browser_and_never_writes_files(db, tmp_path):
    await _add(db, source="browser", title="a webpage")
    await _add(db, source="ide", title="Cursor chat about WAL")
    marker = tmp_path / "README.md"
    card = await queue_ide_journal_draft(db, paused=False, now=datetime.now(UTC))
    assert card is not None
    assert card.payload["draft_kind"] == "journal"
    assert "WAL" in card.payload["body"]
    assert "webpage" not in card.payload["body"]
    assert card.payload["published"] is False
    assert not marker.exists()

    approved = await ReviewQueue(db).decide(card.id, "approve")
    assert approved.card.payload["published"] is False
    assert not marker.exists()
    assert not (tmp_path / "README.md").exists()


@pytest.mark.asyncio
async def test_ide_readme_draft_and_pause(db):
    await _add(db, source="ide", title="terminal error: locked")
    paused = await queue_ide_readme_draft(db, paused=True)
    assert paused is None
    card = await queue_ide_readme_draft(db, paused=False)
    assert card is not None
    assert card.payload["draft_kind"] == "doc"
    assert "Draft README" in card.payload["body"]
    assert "locked" in card.payload["body"]
    assert card.payload["published"] is False

    async def load(session):
        return await session.get(DraftArtifact, int(card.payload["artifact_id"]))

    art = await db.read(load)
    assert art is not None
    assert art.published == "false"


@pytest.mark.asyncio
async def test_drafts_cmd_queues_journal(settings, db):
    await _add(db, source="ide", title="composer session")
    settings.allowed_telegram_user_ids = "42"
    app = MagicMock()
    app.state.capture_paused = False
    svc = BotServices(settings=settings, db=db, app=app)
    ctx = MagicMock()
    ctx.bot_data = {BOT_DATA_KEY: svc}
    ctx.args = ["journal"]
    update = MagicMock()
    update.effective_user.id = 42
    update.message.reply_text = AsyncMock()
    await drafts_cmd(update, ctx)
    text = update.message.reply_text.await_args.args[0]
    assert "journal draft" in text
    assert "does not write files" in text
