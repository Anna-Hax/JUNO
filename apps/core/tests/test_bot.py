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
    jobs_cmd,
    pause_cmd,
    prune_cmd,
    resume_cmd,
    start_cmd,
    status_cmd,
    text_msg,
    voice_msg,
)
from juno.bot.services import (
    BOT_DATA_KEY,
    BotServices,
    format_digest,
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
from juno.models import AppSetting, Capture
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
            source_type=str(kwargs.get("source_type") or "telegram"),
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


def test_format_digest_groups_browser_reading():
    from datetime import UTC, datetime

    now = datetime.now(UTC)
    browser = Capture(
        id=1,
        source_type="browser",
        title="Rust book",
        status="committed",
        captured_at=now,
    )
    upload = Capture(
        id=2,
        source_type="upload",
        title="Notes",
        status="committed",
        captured_at=now,
    )
    text = format_digest([upload, browser], "today")
    assert "Browser reading (1):" in text
    assert "Uploads / other (1):" in text
    assert "Rust book" in text


def test_format_digest_groups_ide_chats_and_errors():
    from datetime import UTC, datetime

    now = datetime.now(UTC)
    chat = Capture(
        id=3,
        source_type="ide",
        title="Fix sqlite lock",
        status="committed",
        captured_at=now,
        raw_json={"kind": "cursor_chat"},
    )
    err = Capture(
        id=4,
        source_type="ide",
        title="database is locked",
        status="committed",
        captured_at=now,
        raw_json={"kind": "cursor_error"},
    )
    upload = Capture(
        id=2,
        source_type="upload",
        title="Notes",
        status="committed",
        captured_at=now,
    )
    text = format_digest([upload, chat, err], "week")
    assert "IDE chats (1):" in text
    assert "IDE errors (1):" in text
    assert "Uploads / other (1):" in text
    assert "Fix sqlite lock" in text
    assert "database is locked" in text


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
    assert commands >= {
        "start",
        "help",
        "digest",
        "pause",
        "resume",
        "status",
        "review",
        "cards",
        "drafts",
        "gaps",
        "trust",
        "prune",
    }


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
    assert "/jobs" in body
    assert "/review" in body
    assert "/cards" in body
    assert "/drafts" in body
    assert "/gaps" in body
    assert "/trust" in body
    assert "/prune" in body
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
async def test_slack_url_requires_opt_in(allowed_settings):
    from juno.bot.services import is_slack_url

    assert is_slack_url("https://acme.slack.com/archives/C123/p1")
    pipeline = FakePipeline()
    svc = _svc(allowed_settings, pipeline=pipeline, app=create_app(allowed_settings))
    update = _update(ALLOWED_ID, "https://acme.slack.com/archives/C123/p1")
    await text_msg(update, _context(svc))
    assert pipeline.calls == []
    assert "Slack forward is off" in update.message.reply_text.await_args.args[0]


@pytest.mark.asyncio
async def test_slack_url_ingests_when_enabled(allowed_settings, db):
    from juno.hitl.queue import KIND_MOBILE_BATCH, ReviewQueue

    allowed_settings.juno_slack_forward = True
    pipeline = FakePipeline()
    svc = _svc(allowed_settings, db=db, pipeline=pipeline, app=create_app(allowed_settings, db=db))
    update = _update(ALLOWED_ID, "https://acme.slack.com/archives/C123/p1")
    await text_msg(update, _context(svc))
    assert pipeline.calls[0][0] == "url"
    assert pipeline.calls[0][2]["source_type"] == "slack"
    reply = update.message.reply_text.await_args.args[0]
    assert "Queued for /review" in reply
    card = await ReviewQueue(db).next_open()
    assert card is not None
    assert card.kind == KIND_MOBILE_BATCH
    assert "Slack" in card.payload["title"]


@pytest.mark.asyncio
async def test_prune_confirm_queues_hitl(allowed_settings, db):
    from datetime import UTC, datetime, timedelta

    from sqlalchemy.ext.asyncio import AsyncSession

    from juno.graph.vectors import VectorStore
    from juno.hitl.queue import KIND_PRUNE, ReviewQueue
    from juno.ingest.pipeline import IngestPipeline
    from juno.llm.embedder import StubEmbedder
    from juno.models import Capture

    allowed_settings.juno_prune_min_age_days = 90
    vectors = VectorStore(allowed_settings, StubEmbedder())
    pipe = IngestPipeline(db, vectors=vectors)
    result = await pipe.ingest_text("old dust", source_type="upload", title="dust")

    async def age(session: AsyncSession) -> None:
        cap = await session.get(Capture, result.capture_id)
        assert cap is not None
        cap.captured_at = datetime.now(UTC) - timedelta(days=100)

    await db.write(age)
    svc = _svc(allowed_settings, db=db, vectors=vectors)
    listed = _update(ALLOWED_ID, "/prune")
    await prune_cmd(listed, _context(svc))
    preview = listed.message.reply_text.await_args.args[0]
    assert "Nothing is deleted" in preview
    queued = _update(ALLOWED_ID, "/prune confirm")
    await prune_cmd(queued, _context(svc, args=["confirm"]))
    assert "Queued prune" in queued.message.reply_text.await_args.args[0]
    card = await ReviewQueue(db).next_open()
    assert card is not None
    assert card.kind == KIND_PRUNE
    assert result.capture_id in card.payload["capture_ids"]


@pytest.mark.asyncio
async def test_forward_queues_mobile_hitl(allowed_settings, db):
    from juno.hitl.queue import KIND_MOBILE_BATCH, ReviewQueue
    from juno.ingest.pipeline import IngestPipeline

    pipe = IngestPipeline(db)
    svc = _svc(allowed_settings, db=db, pipeline=pipe, app=create_app(allowed_settings, db=db))
    fwd = _update(ALLOWED_ID, "a forwarded phone note", forwarded=True)
    await text_msg(fwd, _context(svc))
    body = fwd.message.reply_text.await_args.args[0]
    assert "Queued for /review" in body
    card = await ReviewQueue(db).next_open()
    assert card is not None
    assert card.kind == KIND_MOBILE_BATCH


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
async def test_jobs_cmd_lists_and_toggles_daily(allowed_settings, db):
    from juno.jobs import DIGEST_DAILY_JOB_ID, load_job_enabled_overrides, start_jobs, stop_jobs

    app = create_app(allowed_settings, db=db)
    start_jobs(app)
    svc = _svc(allowed_settings, db=db, app=app)
    try:
        listing = _update(ALLOWED_ID, "/jobs")
        await jobs_cmd(listing, _context(svc))
        body = listing.message.reply_text.await_args.args[0]
        assert "digest_daily" in body
        off = _update(ALLOWED_ID, "/jobs")
        await jobs_cmd(off, _context(svc, args=["daily", "off"]))
        assert "off" in off.message.reply_text.await_args.args[0]
        stored = await load_job_enabled_overrides(db)
        assert stored[DIGEST_DAILY_JOB_ID] is False
    finally:
        stop_jobs(app)


@pytest.mark.asyncio
async def test_status_reports_pause_and_health(allowed_settings, db):
    app = create_app(allowed_settings, db=db)
    app.state.capture_paused = True
    app.state.llm_healthy = False
    app.state.embedder = SimpleNamespace(model_id="stub-hash-v1")
    vectors = FakeVectors()
    from juno.jobs.health import record_jobs_health, record_polish_health

    await record_jobs_health(db, detail="digest_daily skipped (paused)", ok=True)
    await record_polish_health(db, detail="polish skipped (paused)", ok=True)
    svc = _svc(allowed_settings, db=db, app=app, vectors=vectors)
    update = _update(ALLOWED_ID, "/status")
    await status_cmd(update, _context(svc))
    body = update.message.reply_text.await_args.args[0]
    assert "Capture: paused" in body
    assert "retrieve-only" in body
    assert "stub-hash-v1" in body
    assert "Serve-down" in body
    assert "jobs:" in body
    assert "polish:" in body
    assert "paused" in body


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


@pytest.mark.asyncio
async def test_voice_note_is_transcribed_and_ingested(allowed_settings):
    from juno.llm.transcribe import StubTranscriber

    pipeline = FakePipeline()
    app = create_app(allowed_settings)
    app.state.transcriber = StubTranscriber("hello from the phone")
    svc = _svc(allowed_settings, pipeline=pipeline, app=app)
    update = _update(ALLOWED_ID)
    tg_file = MagicMock()
    tg_file.download_as_bytearray = AsyncMock(return_value=bytearray(b"ogg-bytes"))
    voice = MagicMock()
    voice.duration = 2
    voice.get_file = AsyncMock(return_value=tg_file)
    update.message.voice = voice
    await voice_msg(update, _context(svc))
    assert pipeline.calls[0][0] == "text"
    assert pipeline.calls[0][1] == "hello from the phone"
    assert pipeline.calls[0][2]["raw"]["kind"] == "voice"
    assert "Captured #7" in update.message.reply_text.await_args.args[0]


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


@pytest.mark.asyncio
async def test_related_upload_captures_finds_upload_for_browser_hit(db):
    from juno.bot.services import related_upload_captures
    from juno.ingest.pipeline import IngestPipeline
    from juno.rag.engine import SourcedHit

    pipeline = IngestPipeline(db)
    await pipeline.ingest_text(
        "Saved Rust ownership notes from inbox.",
        source_type="upload",
        title="Rust ownership notes",
    )
    hits = [
        SourcedHit(
            chroma_id="c2-n0",
            text="Rust book",
            score=0.9,
            capture_id=2,
            title="Rust ownership guide",
            uri="https://example.com/rust",
            source_type="browser",
        )
    ]
    related = await related_upload_captures(db, browser_hits=hits)
    assert len(related) == 1
    assert related[0].source_type == "upload"
    assert "Rust" in (related[0].title or "")


@pytest.mark.asyncio
async def test_related_captures_links_ide_error_to_browser(db):
    from juno.bot.services import related_captures
    from juno.ingest.pipeline import IngestPipeline
    from juno.rag.engine import SourcedHit

    pipeline = IngestPipeline(db)
    await pipeline.ingest_payload(
        {
            "source_type": "browser",
            "uri": "https://github.com/example/sqlite-lock",
            "title": "database is locked GitHub issue",
            "text": "sqlite database is locked",
        }
    )
    hits = [
        SourcedHit(
            chroma_id="c9-n0",
            text="database is locked Traceback ingest.py",
            score=0.9,
            capture_id=9,
            title="database is locked",
            uri="cursor://error/abc/1",
            source_type="ide",
        )
    ]
    related = await related_captures(db, hits=hits, source_types=("browser", "upload"))
    assert related
    assert related[0].source_type == "browser"
    assert "locked" in (related[0].title or "").lower()
