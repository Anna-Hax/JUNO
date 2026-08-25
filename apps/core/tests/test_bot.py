from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from juno.api import create_app
from juno.bot.handlers import (
    digest_cmd,
    document_msg,
    help_cmd,
    pause_cmd,
    resume_cmd,
    start_cmd,
    status_cmd,
    text_msg,
)
from juno.bot.services import (
    BOT_DATA_KEY,
    BotServices,
    format_retrieve_reply,
    load_capture_paused,
    persist_capture_paused,
    single_http_url,
    user_allowed,
)
from juno.config import Settings
from juno.graph.db import Database
from juno.graph.vectors import VectorHit
from juno.ingest.pipeline import IngestPipeline, IngestResult
from juno.models import AppSetting
from juno.runtime import build_telegram_application

ALLOWED_ID = 42
STRANGER_ID = 99


@pytest.fixture
def allowed_settings(settings):
    return Settings(
        juno_data_dir=settings.juno_data_dir,
        juno_inbox_dir=settings.juno_inbox_dir,
        embedding_backend="stub",
        juno_api_token="test-token",
        telegram_bot_token="",
        allowed_telegram_user_ids=str(ALLOWED_ID),
    )


@pytest.fixture
async def db(allowed_settings):
    database = Database(allowed_settings)
    await database.migrate()
    yield database
    await database.dispose()


class FakePipeline:
    def __init__(self) -> None:
        self.calls: list[tuple] = []

    async def ingest_text(self, text, **kwargs):  # noqa: ANN001
        self.calls.append(("text", text, kwargs))
        return IngestResult(
            accepted=True,
            source_type=str(kwargs.get("source_type") or "telegram"),
            status="committed",
            capture_id=7,
            chunk_count=1,
            title=kwargs.get("title"),
        )

    async def ingest_url(self, url, **kwargs):  # noqa: ANN001
        self.calls.append(("url", url, kwargs))
        return IngestResult(
            accepted=True,
            source_type="telegram",
            status="committed",
            capture_id=8,
            chunk_count=2,
            uri=url,
        )

    async def ingest_path(self, path, **kwargs):  # noqa: ANN001
        self.calls.append(("path", path, kwargs))
        return IngestResult(
            accepted=True,
            source_type="telegram",
            status="committed",
            capture_id=9,
            chunk_count=1,
            title=Path(path).name,
        )


class FakeVectors:
    collection_name = "juno-stub-hash-v1"

    def __init__(self, hits: list[VectorHit] | None = None) -> None:
        self.hits = hits or []
        self.queries: list[tuple[str, int]] = []

    async def query_async(self, text: str, *, n_results: int = 8) -> list[VectorHit]:
        self.queries.append((text, n_results))
        return self.hits

    def count(self) -> int:
        return len(self.hits)


def _context(svc: BotServices, args: list[str] | None = None) -> MagicMock:
    ctx = MagicMock()
    ctx.bot_data = {BOT_DATA_KEY: svc}
    ctx.args = args or []
    return ctx


def _update(user_id: int, text: str | None = None, *, forwarded: bool = False) -> MagicMock:
    update = MagicMock()
    update.effective_user = SimpleNamespace(id=user_id)
    update.message = MagicMock()
    update.message.text = text
    update.message.reply_text = AsyncMock()
    update.message.forward_origin = object() if forwarded else None
    update.message.forward_date = None
    update.message.forward_from = None
    update.message.forward_from_chat = None
    update.message.forward_sender_name = "Alice" if forwarded else None
    update.message.document = None
    return update


def _svc(allowed_settings, *, app=None, db=None, pipeline=None, vectors=None) -> BotServices:
    return BotServices(
        settings=allowed_settings,
        db=db,
        pipeline=pipeline,
        vectors=vectors,
        app=app,
    )


def test_user_allowed_empty_allowlist_rejects_everyone(settings):
    assert not user_allowed(ALLOWED_ID, settings)
    assert not user_allowed(None, settings)


def test_user_allowed_stranger_ignored(allowed_settings):
    assert not user_allowed(STRANGER_ID, allowed_settings)
    assert user_allowed(ALLOWED_ID, allowed_settings)


def test_single_http_url():
    assert single_http_url("https://example.test/a") == "https://example.test/a"
    assert single_http_url("see https://example.test/a") is None
    assert single_http_url("not a url") is None


def test_format_retrieve_reply_empty():
    text = format_retrieve_reply("rust", [])
    assert "Nothing in the graph" in text


def test_format_retrieve_reply_hits():
    hit = VectorHit(
        id="c1-n0",
        text="Ownership in Rust is checked at compile time.",
        metadata={"capture_id": 1, "source_type": "upload"},
        distance=0.2,
    )
    text = format_retrieve_reply("rust", [hit])
    assert "upload #1" in text
    assert "80%" in text
    assert "Ownership in Rust" in text


def test_build_telegram_application_registers_commands(allowed_settings):
    settings = allowed_settings.model_copy(update={"telegram_bot_token": "1:test-token"})
    app = build_telegram_application(settings)
    assert app is not None
    commands: set[str] = set()
    for group in app.handlers.values():
        for handler in group:
            commands.update(getattr(handler, "commands", set()))
    assert commands >= {"start", "help", "digest", "pause", "resume", "status", "review"}


@pytest.mark.asyncio
async def test_stranger_commands_are_ignored(allowed_settings):
    svc = _svc(allowed_settings, pipeline=FakePipeline(), vectors=FakeVectors())
    ctx = _context(svc)
    update = _update(STRANGER_ID, "/start")
    await start_cmd(update, ctx)
    await help_cmd(update, ctx)
    await pause_cmd(update, ctx)
    query = _update(STRANGER_ID, "hello")
    await text_msg(query, ctx)
    update.message.reply_text.assert_not_called()
    query.message.reply_text.assert_not_called()


@pytest.mark.asyncio
async def test_start_and_help_reply_for_allowlisted_user(allowed_settings):
    svc = _svc(allowed_settings)
    ctx = _context(svc)
    start = _update(ALLOWED_ID, "/start")
    await start_cmd(start, ctx)
    start.message.reply_text.assert_awaited()
    assert "Juno online" in start.message.reply_text.await_args.args[0]

    help_update = _update(ALLOWED_ID, "/help")
    await help_cmd(help_update, ctx)
    body = help_update.message.reply_text.await_args.args[0]
    assert "/pause" in body
    assert "/digest" in body
    assert "/review" in body
    assert "Approve" in body


@pytest.mark.asyncio
async def test_text_query_returns_retrieve_hits(allowed_settings):
    hits = [
        VectorHit(
            id="c3-n0",
            text="Borrowing lets you reference data without taking ownership.",
            metadata={"capture_id": 3, "source_type": "upload"},
            distance=0.1,
        )
    ]
    vectors = FakeVectors(hits)
    svc = _svc(allowed_settings, vectors=vectors)
    update = _update(ALLOWED_ID, "what do I know about borrowing?")
    await text_msg(update, _context(svc))
    reply = update.message.reply_text.await_args.args[0]
    assert "Retrieve-only" in reply
    assert "borrowing" in reply.lower()
    assert vectors.queries[0][0] == "what do I know about borrowing?"


@pytest.mark.asyncio
async def test_url_and_forward_are_captured(allowed_settings):
    pipeline = FakePipeline()
    svc = _svc(allowed_settings, pipeline=pipeline, app=create_app(allowed_settings))
    url_update = _update(ALLOWED_ID, "https://example.test/rust")
    await text_msg(url_update, _context(svc))
    assert pipeline.calls[0][0] == "url"
    assert "Captured #8" in url_update.message.reply_text.await_args.args[0]

    fwd = _update(ALLOWED_ID, "a forwarded note about ownership", forwarded=True)
    await text_msg(fwd, _context(svc))
    assert pipeline.calls[1][0] == "text"
    assert pipeline.calls[1][1] == "a forwarded note about ownership"
    assert "Captured #7" in fwd.message.reply_text.await_args.args[0]


@pytest.mark.asyncio
async def test_pause_blocks_telegram_and_api_ingest(allowed_settings, db):
    pipeline = FakePipeline()
    app = create_app(allowed_settings, db=db, pipeline=IngestPipeline(db))
    svc = _svc(allowed_settings, db=db, pipeline=pipeline, app=app)
    pause = _update(ALLOWED_ID, "/pause")
    await pause_cmd(pause, _context(svc))
    assert app.state.capture_paused is True
    assert "paused" in pause.message.reply_text.await_args.args[0].lower()

    blocked = _update(ALLOWED_ID, "https://example.test/nope")
    await text_msg(blocked, _context(svc))
    assert pipeline.calls == []
    assert "paused" in blocked.message.reply_text.await_args.args[0].lower()

    async def read_flag(session):
        row = await session.get(AppSetting, "capture_paused")
        return row.value if row else None

    assert await db.read(read_flag) == "true"
    assert await load_capture_paused(db) is True

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/ingest",
            json={"source_type": "upload", "text": "should block"},
            headers={"Authorization": "Bearer test-token"},
        )
    assert resp.status_code == 423


@pytest.mark.asyncio
async def test_resume_clears_pause_and_scans_inbox(allowed_settings, db):
    app = create_app(allowed_settings, db=db)
    watcher = MagicMock()
    watcher.scan_existing = AsyncMock()
    app.state.inbox_watcher = watcher
    svc = _svc(allowed_settings, db=db, app=app)
    await persist_capture_paused(db, True)
    app.state.capture_paused = True

    resume = _update(ALLOWED_ID, "/resume")
    await resume_cmd(resume, _context(svc))
    assert app.state.capture_paused is False
    assert await load_capture_paused(db) is False
    watcher.scan_existing.assert_awaited()


@pytest.mark.asyncio
async def test_digest_lists_recent_captures(allowed_settings, db):
    pipe = IngestPipeline(db)
    await pipe.ingest_text("Ownership notes from today", source_type="upload", title="rust")
    svc = _svc(allowed_settings, db=db)
    update = _update(ALLOWED_ID, "/digest")
    await digest_cmd(update, _context(svc, args=["today"]))
    body = update.message.reply_text.await_args.args[0]
    assert "Digest today" in body
    assert "rust" in body


@pytest.mark.asyncio
async def test_status_reports_pause_and_health(allowed_settings, db):
    app = create_app(allowed_settings, db=db)
    app.state.capture_paused = True
    app.state.llm_healthy = False
    app.state.embedder = SimpleNamespace(model_id="stub-hash-v1")
    vectors = FakeVectors()
    svc = _svc(allowed_settings, db=db, app=app, vectors=vectors)
    update = _update(ALLOWED_ID, "/status")
    await status_cmd(update, _context(svc))
    body = update.message.reply_text.await_args.args[0]
    assert "Capture: paused" in body
    assert "retrieve-only" in body
    assert "stub-hash-v1" in body


@pytest.mark.asyncio
async def test_document_is_ingested(allowed_settings):
    pipeline = FakePipeline()
    svc = _svc(allowed_settings, pipeline=pipeline, app=create_app(allowed_settings))
    update = _update(ALLOWED_ID)
    file = MagicMock()

    async def _download(custom_path):  # noqa: ANN001
        Path(custom_path).write_text("hi")

    file.download_to_drive = AsyncMock(side_effect=_download)
    doc = MagicMock()
    doc.file_name = "note.md"
    doc.file_unique_id = "abc123"
    doc.get_file = AsyncMock(return_value=file)
    update.message.document = doc
    await document_msg(update, _context(svc))
    assert pipeline.calls[0][0] == "path"
    assert "Captured #9" in update.message.reply_text.await_args.args[0]
    dest = pipeline.calls[0][1]
    assert dest.name == "abc123.md"
    assert not dest.exists()


class _FakeChat:
    def __init__(self, answer: str) -> None:
        self.answer = answer
        self.complete_calls = 0

    async def healthy(self, *, timeout: float = 3.0) -> bool:  # noqa: ARG002
        return True

    async def complete(self, system: str, messages: list[dict[str, str]], **kwargs):  # noqa: ANN001
        self.complete_calls += 1
        return self.answer


@pytest.mark.asyncio
async def test_text_query_uses_rag_engine_when_llm_healthy(allowed_settings, db):
    from juno.graph.vectors import VectorStore
    from juno.llm.embedder import StubEmbedder

    note = (
        "Juno telegram rag marker rust-ownership-xyz. "
        "Ownership in Rust means each value has a single owner."
    )
    vectors = VectorStore(allowed_settings, StubEmbedder())
    pipe = IngestPipeline(db, vectors=vectors)
    await pipe.ingest_text(note, source_type="upload", title="Rust notes")
    app = create_app(allowed_settings, db=db, vectors=vectors, pipeline=pipe)
    chat = _FakeChat("Each value has a single owner [1].")
    app.state.chat = chat
    svc = _svc(allowed_settings, db=db, app=app, vectors=vectors, pipeline=pipe)
    update = _update(ALLOWED_ID, note)
    await text_msg(update, _context(svc))
    body = update.message.reply_text.await_args.args[0]
    assert "Each value has a single owner [1]." in body
    assert "Rust notes" in body
    assert "Confidence:" in body
    assert chat.complete_calls == 1
