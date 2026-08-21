from __future__ import annotations

import pytest
from sqlalchemy import select

from juno.graph.db import Database
from juno.llm.embedder import StubEmbedder, create_embedder
from juno.models import AppSetting, Capture


@pytest.mark.asyncio
async def test_db_init_and_write_queue(settings):
    db = Database(settings)
    await db.migrate()

    async def insert(session):
        session.add(
            Capture(
                source_type="upload",
                uri="file://note.md",
                text="hello juno",
                status="committed",
            )
        )
        session.add(AppSetting(key="capture_paused", value="false"))
        session.add(AppSetting(key="embedding_model", value="stub-hash-v1"))

    await db.write(insert)

    async def count(session):
        result = await session.execute(select(Capture))
        return list(result.scalars())

    rows = await db.read(count)
    assert len(rows) == 1
    assert rows[0].text == "hello juno"
    await db.dispose()


def test_stub_embedder_deterministic():
    emb = StubEmbedder()
    a = emb.embed(["rust ownership"])
    b = emb.embed(["rust ownership"])
    c = emb.embed(["different"])
    assert a == b
    assert a != c
    assert len(a[0]) == emb.dimensions


def test_create_embedder_stub():
    emb = create_embedder("stub", "ignored")
    assert emb.model_id == "stub-hash-v1"
    assert len(emb.embed(["x"])[0]) == 64


def test_health_endpoint(settings):
    from fastapi.testclient import TestClient

    from juno.api import create_app

    app = create_app(settings)
    client = TestClient(app)
    assert client.get("/health").json() == {"status": "ok"}


def test_ingest_requires_token(settings):
    from fastapi.testclient import TestClient

    from juno.api import create_app

    app = create_app(settings)
    client = TestClient(app)
    assert client.post("/ingest", json={"source_type": "browser"}).status_code == 401
    ok = client.post(
        "/ingest",
        json={"source_type": "browser"},
        headers={"Authorization": "Bearer test-token"},
    )
    assert ok.status_code == 200
    assert ok.json()["accepted"] is True


def test_status_requires_token(settings):
    from fastapi.testclient import TestClient

    from juno.api import create_app

    app = create_app(settings)
    client = TestClient(app)
    assert client.get("/status").status_code == 401
    resp = client.get("/status", headers={"Authorization": "Bearer test-token"})
    assert resp.status_code == 200
    assert "capture_paused" in resp.json()
