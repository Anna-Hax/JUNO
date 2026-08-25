from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from telegram.ext import CallbackQueryHandler, CommandHandler

from juno.bot.review import parse_review_callback, review_callback, review_cmd, review_keyboard
from juno.graph.db import Database
from juno.hitl.queue import EDGE_COMMITTED, EDGE_PENDING, ReviewQueue
from juno.models import Edge
from juno.runtime import build_telegram_application


@pytest.fixture
def allowed_settings(settings):
    return settings.model_copy(update={"allowed_telegram_user_ids": "42"})


@pytest.fixture
async def queue(allowed_settings):
    db = Database(allowed_settings)
    await db.migrate()
    q = ReviewQueue(db)
    yield q
    await db.dispose()


def _message_update(user_id: int) -> MagicMock:
    update = MagicMock()
    update.effective_user.id = user_id
    update.message.reply_text = AsyncMock()
    update.callback_query = None
    return update


def _callback_update(user_id: int, data: str) -> MagicMock:
    update = MagicMock()
    update.effective_user.id = user_id
    update.message = None
    update.callback_query = MagicMock()
    update.callback_query.data = data
    update.callback_query.answer = AsyncMock()
    update.callback_query.edit_message_text = AsyncMock()
    return update


def _context(settings, queue: ReviewQueue | None) -> MagicMock:
    ctx = MagicMock()
    ctx.application.bot_data = {"settings": settings, "review": queue}
    return ctx


def test_parse_review_callback():
    assert parse_review_callback("rev:12:approve") == (12, "approve")
    assert parse_review_callback("rev:12:reject") == (12, "reject")
    assert parse_review_callback("rev:12:skip") == (12, "skip")
    assert parse_review_callback("rev:nope:approve") is None
    assert parse_review_callback("other:1:approve") is None


def test_review_keyboard_callback_data():
    markup = review_keyboard(7)
    labels = [btn.text for row in markup.inline_keyboard for btn in row]
    data = [btn.callback_data for row in markup.inline_keyboard for btn in row]
    assert labels == ["Approve", "Reject", "Skip"]
    assert data == ["rev:7:approve", "rev:7:reject", "rev:7:skip"]


@pytest.mark.asyncio
async def test_review_cmd_ignores_strangers(allowed_settings, queue):
    update = _message_update(99)
    await review_cmd(update, _context(allowed_settings, queue))
    update.message.reply_text.assert_not_called()


@pytest.mark.asyncio
async def test_review_cmd_empty_queue(allowed_settings, queue):
    update = _message_update(42)
    await review_cmd(update, _context(allowed_settings, queue))
    update.message.reply_text.assert_awaited_once_with("Review queue empty.")


@pytest.mark.asyncio
async def test_review_cmd_shows_pending_merge(allowed_settings, queue):
    card = await queue.propose_merge(from_name="Foo", to_name="Bar", confidence=0.33)
    update = _message_update(42)
    await review_cmd(update, _context(allowed_settings, queue))
    kwargs = update.message.reply_text.await_args
    text = kwargs.args[0]
    markup = kwargs.kwargs["reply_markup"]
    assert f"Review #{card.id}" in text
    assert "Foo" in text
    assert "Bar" in text
    assert "stays pending until you Approve" in text
    data = [btn.callback_data for row in markup.inline_keyboard for btn in row]
    assert f"rev:{card.id}:approve" in data


@pytest.mark.asyncio
async def test_approve_callback_commits_merge(allowed_settings, queue):
    card = await queue.propose_merge(from_name="Src", to_name="Dst", confidence=0.7)
    edge_id = int(card.payload["edge_id"])
    update = _callback_update(42, f"rev:{card.id}:approve")
    await review_callback(update, _context(allowed_settings, queue))

    update.callback_query.answer.assert_awaited()
    edited = update.callback_query.edit_message_text.await_args.args[0]
    assert "Approved" in edited
    assert "Merge is now committed" in edited

    async def load(session):
        edge = await session.get(Edge, edge_id)
        assert edge is not None
        return edge.status

    assert await queue.db.read(load) == EDGE_COMMITTED


@pytest.mark.asyncio
async def test_skip_callback_does_not_commit(allowed_settings, queue):
    card = await queue.propose_merge(from_name="Left", to_name="Right", confidence=0.4)
    edge_id = int(card.payload["edge_id"])
    update = _callback_update(42, f"rev:{card.id}:skip")
    await review_callback(update, _context(allowed_settings, queue))
    edited = update.callback_query.edit_message_text.await_args.args[0]
    assert "Skipped" in edited
    assert "stays in the queue" in edited

    async def load(session):
        edge = await session.get(Edge, edge_id)
        assert edge is not None
        return edge.status

    assert await queue.db.read(load) == EDGE_PENDING


@pytest.mark.asyncio
async def test_review_queue_falls_back_to_juno_bot_data(allowed_settings, queue):
    card = await queue.propose_merge(from_name="X", to_name="Y", confidence=0.5)
    services = MagicMock()
    services.settings = allowed_settings
    services.db = queue.db
    ctx = MagicMock()
    ctx.application.bot_data = {"juno": services}
    update = _message_update(42)
    await review_cmd(update, ctx)
    text = update.message.reply_text.await_args.args[0]
    assert f"Review #{card.id}" in text


def test_telegram_app_registers_review_handlers(allowed_settings):
    settings = allowed_settings.model_copy(update={"telegram_bot_token": "1:test-token"})
    app = build_telegram_application(settings)
    assert app is not None
    handlers = [handler for group in app.handlers.values() for handler in group]
    commands: set[str] = set()
    for handler in handlers:
        if isinstance(handler, CommandHandler):
            commands.update(handler.commands)
    assert "review" in commands
    assert any(isinstance(handler, CallbackQueryHandler) for handler in handlers)
