"""Fixture-backed tests for the Spike S3 Cursor vscdb reader (apps/ide)."""

from __future__ import annotations

import importlib.util
import json
import sqlite3
import sys
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest

from juno.api import create_app
from juno.graph.db import Database
from juno.ingest.pipeline import IngestPipeline
from juno.models import Capture

REPO_ROOT = Path(__file__).resolve().parents[3]
_IDE_MOD = REPO_ROOT / "apps" / "ide" / "cursor_vscdb.py"
_SPEC = importlib.util.spec_from_file_location("cursor_vscdb", _IDE_MOD)
assert _SPEC and _SPEC.loader
_cursor = importlib.util.module_from_spec(_SPEC)
sys.modules["cursor_vscdb"] = _cursor
_SPEC.loader.exec_module(_cursor)

connect_readonly = _cursor.connect_readonly
format_session_text = _cursor.format_session_text
list_sessions = _cursor.list_sessions
load_session = _cursor.load_session
to_ingest_payload = _cursor.to_ingest_payload

COMPOSER_ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
BID_USER = "11111111-1111-1111-1111-111111111111"
BID_TOOL = "22222222-2222-2222-2222-222222222222"
BID_ASST = "33333333-3333-3333-3333-333333333333"
CREATED_MS = 1_788_307_200_000  # 2026-09-02 00:00:00 UTC
UPDATED_MS = 1_788_310_800_000  # 2026-09-02 01:00:00 UTC


def _write_fixture(path: Path) -> None:
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE cursorDiskKV (key TEXT PRIMARY KEY, value BLOB)")
    conn.execute(
        "CREATE TABLE composerHeaders ("
        "composerId TEXT, workspaceId TEXT, createdAt INTEGER, lastUpdatedAt INTEGER, "
        "isArchived INTEGER, isSubagent INTEGER, recency INTEGER, checkpointAt INTEGER, value TEXT)"
    )
    header = {
        "composerId": COMPOSER_ID,
        "name": "Fix sqlite lock",
        "createdAt": CREATED_MS,
        "lastUpdatedAt": UPDATED_MS,
        "unifiedMode": "agent",
        "trackedGitRepos": [{"repoPath": r"D:\proj\demo"}],
    }
    composer = {
        "composerId": COMPOSER_ID,
        "name": "Fix sqlite lock",
        "createdAt": CREATED_MS,
        "lastUpdatedAt": UPDATED_MS,
        "unifiedMode": "agent",
        "fullConversationHeadersOnly": [
            {"bubbleId": BID_USER, "type": 1, "createdAt": "2026-09-02T00:00:00Z"},
            {"bubbleId": BID_TOOL, "type": 2},
            {"bubbleId": BID_ASST, "type": 2, "createdAt": "2026-09-02T00:01:00Z"},
        ],
    }
    user_bubble = {"bubbleId": BID_USER, "type": 1, "text": "database is locked on ingest"}
    tool_bubble = {"bubbleId": BID_TOOL, "type": 2, "text": ""}
    asst_bubble = {
        "bubbleId": BID_ASST,
        "type": 2,
        "text": "Enable WAL and serialize writes through Database.write().",
    }
    conn.execute(
        "INSERT INTO composerHeaders "
        "(composerId, workspaceId, createdAt, lastUpdatedAt, isArchived, value) "
        "VALUES (?, ?, ?, ?, 0, ?)",
        (COMPOSER_ID, "ws-demo", CREATED_MS, UPDATED_MS, json.dumps(header)),
    )
    conn.execute(
        "INSERT INTO cursorDiskKV (key, value) VALUES (?, ?)",
        (f"composerData:{COMPOSER_ID}", json.dumps(composer)),
    )
    for bid, blob in (
        (BID_USER, user_bubble),
        (BID_TOOL, tool_bubble),
        (BID_ASST, asst_bubble),
    ):
        conn.execute(
            "INSERT INTO cursorDiskKV (key, value) VALUES (?, ?)",
            (f"bubbleId:{COMPOSER_ID}:{bid}", json.dumps(blob)),
        )
    conn.commit()
    conn.close()


@pytest.fixture
def vscdb(tmp_path: Path) -> Path:
    path = tmp_path / "state.vscdb"
    _write_fixture(path)
    return path


@pytest.fixture
async def db(settings):
    database = Database(settings)
    await database.migrate()
    yield database
    await database.dispose()


@pytest.fixture
def pipeline(db):
    return IngestPipeline(db)


def test_list_and_load_skips_empty_tool_bubbles(vscdb: Path):
    conn = connect_readonly(vscdb)
    try:
        listed = list_sessions(conn)
        assert len(listed) == 1
        assert listed[0].composer_id == COMPOSER_ID
        assert listed[0].name == "Fix sqlite lock"
        assert listed[0].workspace_path == r"D:\proj\demo"

        loaded = load_session(conn, COMPOSER_ID)
        assert loaded is not None
        assert [b.role for b in loaded.bubbles] == ["user", "assistant"]
        assert "database is locked" in loaded.bubbles[0].text
        assert "WAL" in loaded.bubbles[1].text
    finally:
        conn.close()


def test_ingest_payload_shape(vscdb: Path):
    conn = connect_readonly(vscdb)
    try:
        loaded = load_session(conn, COMPOSER_ID)
        assert loaded is not None
        payload = to_ingest_payload(loaded)
    finally:
        conn.close()

    assert payload["source_type"] == "ide"
    assert payload["uri"] == f"cursor://composer/{COMPOSER_ID}"
    assert payload["title"] == "Fix sqlite lock"
    assert "user:" in payload["text"]
    raw = payload["raw_json"]
    assert raw["kind"] == "cursor_chat"
    assert raw["composer_id"] == COMPOSER_ID
    assert len(raw["bubbles"]) == 2
    assert payload["visited_at"] == datetime(2026, 9, 2, 1, 0, tzinfo=UTC).isoformat()


@pytest.mark.asyncio
async def test_ide_payload_commits_via_pipeline(db, pipeline: IngestPipeline, vscdb: Path):
    conn = connect_readonly(vscdb)
    try:
        loaded = load_session(conn, COMPOSER_ID)
        assert loaded is not None
        payload = to_ingest_payload(loaded)
    finally:
        conn.close()

    result = await pipeline.ingest_payload(payload)
    assert result.status == "committed"
    assert result.source_type == "ide"
    assert result.capture_id is not None

    async def read(session):
        row = await session.get(Capture, result.capture_id)
        assert row is not None
        assert row.source_type == "ide"
        assert row.uri == payload["uri"]
        assert row.raw_json is not None
        assert row.raw_json.get("composer_id") == COMPOSER_ID
        return row

    await db.read(read)


@pytest.mark.asyncio
async def test_ide_ingest_http_roundtrip(db, pipeline: IngestPipeline, settings):
    app = create_app(settings, db=db, pipeline=pipeline)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/ingest",
            json={
                "source_type": "ide",
                "uri": "cursor://composer/smoke",
                "title": "Spike S3 smoke",
                "text": "user:\nhello composer\n",
            },
            headers={"Authorization": "Bearer test-token"},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["accepted"] is True
    assert body["source_type"] == "ide"
    assert body["status"] == "committed"


def test_format_session_text_includes_workspace(vscdb: Path):
    conn = connect_readonly(vscdb)
    try:
        loaded = load_session(conn, COMPOSER_ID)
        assert loaded is not None
        text = format_session_text(loaded)
    finally:
        conn.close()
    assert "Workspace:" in text
    assert "demo" in text
    assert "database is locked" in text
