from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
from sqlalchemy import select

from juno.api import create_app
from juno.graph.db import Database
from juno.ingest.chunking import chunk_text
from juno.ingest.extractors import extract_html, extract_path
from juno.ingest.pipeline import IngestPipeline
from juno.ingest.watcher import InboxWatcher, should_skip
from juno.models import Capture, Chunk, ModuleHealth

ARTICLE_HTML = """<!DOCTYPE html>
<html lang="en"><head><title>Rust Ownership Notes</title></head>
<body>
<article>
<h1>Rust Ownership Notes</h1>
<p>Ownership in Rust is a set of rules that the compiler checks at compile time.
Each value has a single owner, and when that owner goes out of scope the value is dropped.</p>
<p>Borrowing lets you reference data without taking ownership. Mutable borrows are exclusive.
These notes were captured so Juno can retrieve them later during debugging sessions.</p>
<p>Cross-project pattern: the same borrow-checker error showed up
in both the CLI and the API crate.</p>
</article>
</body></html>
"""


class FakeVectors:
    def __init__(self) -> None:
        self.ids: list[str] = []
        self.texts: list[str] = []

    async def upsert_async(self, *, ids, texts, metadatas=None):  # noqa: ANN001
        self.ids.extend(ids)
        self.texts.extend(texts)


@pytest.fixture
async def db(settings):
    database = Database(settings)
    await database.migrate()
    yield database
    await database.dispose()


@pytest.fixture
def pipeline(db):
    return IngestPipeline(db)


def _write_pdf(path: Path, text: str) -> None:
    import pymupdf

    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), text)
    doc.save(str(path))
    doc.close()


def test_chunk_text_empty_and_short():
    assert chunk_text("") == []
    assert chunk_text("  hello  ") == ["hello"]
    parts = chunk_text("alpha " * 400, size=40, overlap=10)
    assert len(parts) > 2
    assert all(parts)


def test_should_skip_gitkeep(tmp_path):
    assert should_skip(tmp_path / ".gitkeep")
    assert should_skip(tmp_path / "notes.tmp")
    assert not should_skip(tmp_path / "notes.md")


@pytest.mark.asyncio
async def test_extract_txt_and_md(tmp_path):
    note = tmp_path / "note.md"
    note.write_text("# Hello\n\nJuno inbox capture.", encoding="utf-8")
    extracted = await extract_path(note)
    assert "Juno inbox capture" in extracted.text
    assert extracted.title == "note"
    assert extracted.source_type == "upload"


@pytest.mark.asyncio
async def test_extract_pdf(tmp_path):
    pdf = tmp_path / "doc.pdf"
    _write_pdf(pdf, "Hello from a PDF about Juno")
    extracted = await extract_path(pdf)
    assert "Hello from a PDF" in extracted.text


@pytest.mark.asyncio
async def test_extract_html_article():
    extracted = extract_html(ARTICLE_HTML, url="https://example.test/rust")
    assert "Ownership in Rust" in extracted.text
    assert extracted.title == "Rust Ownership Notes"


@pytest.mark.asyncio
async def test_drop_markdown_file_to_capture(settings, pipeline, db):
    path = settings.juno_inbox_dir / "dropped.md"
    path.write_text("Dropped into the inbox for Juno.", encoding="utf-8")
    result = await pipeline.ingest_path(path)
    assert result.status == "committed"
    assert result.capture_id is not None
    assert result.chunk_count == 1

    async def fetch(session):
        capture = await session.get(Capture, result.capture_id)
        chunks = list((await session.execute(select(Chunk))).scalars())
        health = await session.get(ModuleHealth, "ingest")
        return capture, chunks, health

    capture, chunks, health = await db.read(fetch)
    assert capture is not None
    assert capture.status == "committed"
    assert capture.text and "Dropped into the inbox" in capture.text
    assert len(chunks) == 1
    assert chunks[0].chroma_id == f"c{capture.id}-n0"
    assert health is not None
    assert health.last_success_at is not None


@pytest.mark.asyncio
async def test_bad_pdf_records_failed_capture(settings, pipeline, db):
    path = settings.juno_inbox_dir / "corrupt.pdf"
    path.write_bytes(b"this is not a pdf file at all")
    result = await pipeline.ingest_path(path)
    assert result.status == "failed"
    assert result.capture_id is not None
    assert result.error_reason
    assert "pdf" in result.error_reason.lower() or "unreadable" in result.error_reason.lower()

    async def fetch(session):
        capture = await session.get(Capture, result.capture_id)
        chunks = list((await session.execute(select(Chunk))).scalars())
        return capture, chunks

    capture, chunks = await db.read(fetch)
    assert capture is not None
    assert capture.status == "failed"
    assert capture.error_reason
    assert chunks == []


@pytest.mark.asyncio
async def test_vector_upsert_uses_chroma_ids(db):
    vectors = FakeVectors()
    pipe = IngestPipeline(db, vectors=vectors)
    result = await pipe.ingest_text("Indexed for later retrieval.", source_type="upload")
    assert result.status == "committed"
    assert vectors.ids == [f"c{result.capture_id}-n0"]
    assert "Indexed for later retrieval" in vectors.texts[0]


@pytest.mark.asyncio
async def test_ingest_url_with_mock_http(pipeline):
    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == "https://example.test/rust"
        return httpx.Response(200, text=ARTICLE_HTML)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        result = await pipeline.ingest_url("https://example.test/rust", client=client)
    assert result.status == "committed"
    assert result.chunk_count >= 1
    assert result.uri == "https://example.test/rust"


@pytest.mark.asyncio
async def test_inbox_scan_archives_file(settings, pipeline, db):
    inbox = settings.juno_inbox_dir
    dropped = inbox / "scan-me.txt"
    dropped.write_text("Watcher should pick this up.", encoding="utf-8")
    gitkeep = inbox / ".gitkeep"
    gitkeep.write_text("", encoding="utf-8")

    watcher = InboxWatcher(
        inbox,
        pipeline.ingest_path,
        settle_checks=1,
        settle_min_age=0,
    )
    n = await watcher.scan_existing()
    assert n == 1
    assert not dropped.exists()
    archived = inbox / ".processed" / "scan-me.txt"
    assert archived.is_file()
    assert gitkeep.is_file()

    async def count(session):
        return list((await session.execute(select(Capture))).scalars())

    rows = await db.read(count)
    assert len(rows) == 1
    assert rows[0].status == "committed"


@pytest.mark.asyncio
async def test_inbox_scan_archives_bad_pdf(settings, pipeline):
    inbox = settings.juno_inbox_dir
    bad = inbox / "nope.pdf"
    bad.write_bytes(b"%PDF-1.4\nnot really")
    watcher = InboxWatcher(
        inbox,
        pipeline.ingest_path,
        settle_checks=1,
        settle_min_age=0,
    )
    await watcher.scan_existing()
    assert not bad.exists()
    assert (inbox / ".failed" / "nope.pdf").is_file()


@pytest.mark.asyncio
async def test_paused_watcher_leaves_file(settings, pipeline):
    inbox = settings.juno_inbox_dir
    dropped = inbox / "later.md"
    dropped.write_text("wait", encoding="utf-8")
    watcher = InboxWatcher(
        inbox,
        pipeline.ingest_path,
        is_paused=lambda: True,
        settle_checks=1,
        settle_min_age=0,
    )
    await watcher.scan_existing()
    assert dropped.is_file()


@pytest.mark.asyncio
async def test_ingest_api_persists_text(settings, db, pipeline):
    app = create_app(settings, db=db, pipeline=pipeline)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/ingest",
            json={"source_type": "upload", "text": "via api", "title": "note"},
            headers={"Authorization": "Bearer test-token"},
        )
        app.state.capture_paused = True
        blocked = await client.post(
            "/ingest",
            json={"source_type": "upload", "text": "nope"},
            headers={"Authorization": "Bearer test-token"},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["accepted"] is True
    assert body["status"] == "committed"
    assert body["chunk_count"] == 1
    assert blocked.status_code == 423


@pytest.mark.asyncio
async def test_browser_payload_stores_visited_at_and_raw_json(db, pipeline):
    when = datetime(2026, 8, 29, 12, 0, tzinfo=UTC)
    result = await pipeline.ingest_payload(
        {
            "source_type": "browser",
            "uri": "https://example.com/page",
            "title": "Example page",
            "text": "Example page",
            "visited_at": when.isoformat(),
        }
    )
    assert result.status == "committed"
    assert result.capture_id is not None

    async def read(session):
        row = await session.get(Capture, result.capture_id)
        assert row is not None
        assert row.source_type == "browser"
        assert row.uri == "https://example.com/page"
        assert row.title == "Example page"
        assert row.captured_at.replace(tzinfo=UTC) == when
        assert row.raw_json is not None
        assert row.raw_json.get("visited_at") == when.isoformat()
        return row

    await db.read(read)
