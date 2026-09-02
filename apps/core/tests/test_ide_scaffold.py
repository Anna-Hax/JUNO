"""IDE adapter scaffold (#65): config, watermark poll, validate-ide."""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

from juno.graph.db import Database
from juno.ingest.pipeline import IngestPipeline

REPO_ROOT = Path(__file__).resolve().parents[3]
IDE = REPO_ROOT / "apps" / "ide"
if str(IDE) not in sys.path:
    sys.path.insert(0, str(IDE))

from config import load_config  # noqa: E402
from cursor_vscdb import CursorSession  # noqa: E402
from sync import due_sessions, load_watermark, save_watermark  # noqa: E402

VALIDATE = REPO_ROOT / "scripts" / "validate-ide.py"


@pytest.fixture
async def db(settings):
    database = Database(settings)
    await database.migrate()
    yield database
    await database.dispose()


def _session(
    composer_id: str,
    *,
    updated: datetime,
    name: str = "chat",
    workspace: str | None = r"D:\proj\demo",
) -> CursorSession:
    return CursorSession(
        composer_id=composer_id,
        name=name,
        created_at=updated,
        updated_at=updated,
        workspace_path=workspace,
    )


def test_validate_ide_script():
    proc = subprocess.run(
        [sys.executable, str(VALIDATE)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout


def test_load_config_from_dotenv(tmp_path, monkeypatch):
    monkeypatch.delenv("JUNO_API_TOKEN", raising=False)
    monkeypatch.delenv("JUNO_CURSOR_VSCDB", raising=False)
    monkeypatch.delenv("JUNO_API_HOST", raising=False)
    monkeypatch.delenv("JUNO_API_PORT", raising=False)
    monkeypatch.delenv("JUNO_IDE_POLL_SECONDS", raising=False)
    monkeypatch.delenv("JUNO_CURSOR_WORKSPACE", raising=False)
    monkeypatch.delenv("JUNO_IDE_STATE", raising=False)
    env = tmp_path / ".env"
    db = tmp_path / "state.vscdb"
    env.write_text(
        "\n".join(
            [
                "JUNO_API_HOST=127.0.0.1",
                "JUNO_API_PORT=8787",
                "JUNO_API_TOKEN=scaffold-token",
                f"JUNO_CURSOR_VSCDB={db}",
                "JUNO_IDE_POLL_SECONDS=12",
                "JUNO_CURSOR_WORKSPACE=demo",
                f"JUNO_DATA_DIR={tmp_path / 'data'}",
            ]
        ),
        encoding="utf-8",
    )
    cfg = load_config(start=tmp_path)
    assert cfg.api_base_url == "http://127.0.0.1:8787"
    assert cfg.api_token == "scaffold-token"
    assert cfg.global_vscdb == db
    assert cfg.poll_seconds == 12
    assert cfg.workspace_filter == "demo"
    assert cfg.token_is_usable()
    assert cfg.state_path == tmp_path / "data" / "ide-adapter.json"


def test_due_sessions_watermark_and_workspace_filter():
    t0 = datetime(2026, 9, 1, tzinfo=UTC)
    t1 = datetime(2026, 9, 2, tzinfo=UTC)
    t2 = datetime(2026, 9, 3, tzinfo=UTC)
    sessions = [
        _session("new", updated=t2, workspace=r"D:\proj\demo"),
        _session("other", updated=t2, workspace=r"D:\other"),
        _session("old", updated=t0, workspace=r"D:\proj\demo"),
    ]
    due = due_sessions(sessions, watermark=t1, limit=8, workspace_filter="demo")
    assert [s.composer_id for s in due] == ["new"]


def test_watermark_roundtrip(tmp_path):
    path = tmp_path / "ide-adapter.json"
    when = datetime(2026, 9, 2, 12, 0, tzinfo=UTC)
    save_watermark(path, when)
    assert load_watermark(path) == when
    assert json.loads(path.read_text(encoding="utf-8"))["module"] == "ide"


@pytest.mark.asyncio
async def test_ide_ingest_respects_pause(settings, db):
    from juno.api import create_app

    pipeline = IngestPipeline(db)
    app = create_app(settings, db=db, pipeline=pipeline)

    import httpx

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/ingest",
            json={"source_type": "ide", "title": "scaffold", "text": "hi"},
            headers={"Authorization": "Bearer test-token"},
        )
        assert resp.status_code == 200
        app.state.capture_paused = True
        paused = await client.post(
            "/ingest",
            json={"source_type": "ide", "title": "paused", "text": "nope"},
            headers={"Authorization": "Bearer test-token"},
        )
        assert paused.status_code == 423

    from api import post_ingest

    result = post_ingest(
        "http://127.0.0.1:9",
        "x",
        {"source_type": "ide", "text": "offline"},
        timeout=1,
    )
    assert result.ok is False
    assert result.status == 0
