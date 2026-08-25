from __future__ import annotations

import httpx
import pytest

from juno.api import create_app
from juno.graph.db import Database
from juno.graph.vectors import VectorStore
from juno.ingest.pipeline import IngestPipeline
from juno.llm.chat import OfflineProvider
from juno.llm.embedder import StubEmbedder
from juno.rag.engine import similarity_from_distance

NOTE_A = (
    "Juno retrieve citation marker rust-ownership-xyz. "
    "Ownership in Rust means each value has a single owner."
)
NOTE_B = (
    "Unrelated gardening notes about tomatoes and soil pH. "
    "Nothing here mentions compilers or borrowing."
)


class FakeChat:
    def __init__(self, *, healthy: bool = True, answer: str = "", fail: bool = False) -> None:
        self._healthy = healthy
        self._answer = answer
        self.fail = fail
        self.complete_calls = 0
        self.healthy_calls = 0

    async def healthy(self, *, timeout: float = 3.0) -> bool:
        self.healthy_calls += 1
        return self._healthy

    async def complete(self, system: str, messages: list[dict[str, str]], **kwargs):  # noqa: ANN001
        self.complete_calls += 1
        if self.fail:
            raise RuntimeError("LLM offline — use retrieve-only fallback")
        assert "Sources:" in messages[0]["content"]
        assert "Question:" in messages[0]["content"]
        return self._answer


@pytest.fixture
async def db(settings):
    database = Database(settings)
    await database.migrate()
    yield database
    await database.dispose()


@pytest.fixture
def vectors(settings):
    return VectorStore(settings, StubEmbedder())


@pytest.fixture
def pipeline(db, vectors):
    return IngestPipeline(db, vectors=vectors)


async def _client(settings, *, db, vectors, pipeline, chat=None):
    app = create_app(
        settings,
        db=db,
        embedder=StubEmbedder(),
        vectors=vectors,
        pipeline=pipeline,
        chat=chat,
    )
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test"), app


def test_similarity_from_distance_clamps():
    assert similarity_from_distance(0.0) == 1.0
    assert similarity_from_distance(1.0) == 0.0
    assert similarity_from_distance(None) == 0.0
    assert similarity_from_distance(-0.2) == 1.0
    assert similarity_from_distance(1.5) == 0.0


def test_search_requires_token(settings):
    from fastapi.testclient import TestClient

    client = TestClient(create_app(settings))
    assert client.get("/search", params={"q": "rust"}).status_code == 401


@pytest.mark.asyncio
async def test_retrieve_joins_capture_citations(settings, db, vectors, pipeline):
    first = await pipeline.ingest_text(NOTE_A, source_type="upload", title="Rust notes")
    await pipeline.ingest_text(NOTE_B, source_type="upload", title="Garden")
    client, _ = await _client(settings, db=db, vectors=vectors, pipeline=pipeline)
    async with client:
        resp = await client.get(
            "/search",
            params={"q": NOTE_A, "mode": "retrieve"},
            headers={"Authorization": "Bearer test-token"},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["mode"] == "retrieve"
    assert body["answer"] is None
    assert body["results"]
    top = body["results"][0]
    assert top["capture_id"] == first.capture_id
    assert top["title"] == "Rust notes"
    assert top["chroma_id"] == f"c{first.capture_id}-n0"
    assert "rust-ownership-xyz" in top["text"]
    assert top["score"] == pytest.approx(1.0)
    assert body["confidence"] == pytest.approx(1.0)
    assert body["citations"][0]["capture_id"] == first.capture_id


@pytest.mark.asyncio
async def test_retrieve_empty_index(settings, db, vectors, pipeline):
    client, _ = await _client(settings, db=db, vectors=vectors, pipeline=pipeline)
    async with client:
        resp = await client.get(
            "/search",
            params={"q": "nothing ingested yet"},
            headers={"Authorization": "Bearer test-token"},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["results"] == []
    assert body["citations"] == []
    assert body["confidence"] == 0.0
    assert body["mode"] == "retrieve"


@pytest.mark.asyncio
async def test_rag_sourced_answer_requires_citations(settings, db, vectors, pipeline):
    await pipeline.ingest_text(NOTE_A, source_type="upload", title="Rust notes")
    chat = FakeChat(answer="Each value has a single owner [1].")
    client, _ = await _client(settings, db=db, vectors=vectors, pipeline=pipeline, chat=chat)
    async with client:
        resp = await client.get(
            "/search",
            params={"q": NOTE_A, "mode": "rag"},
            headers={"Authorization": "Bearer test-token"},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["mode"] == "rag"
    assert body["answer"] == "Each value has a single owner [1]."
    assert body["citations"]
    assert body["citations"][0]["title"] == "Rust notes"
    assert "[1]" in body["answer"]
    assert chat.complete_calls == 1
    assert body["confidence"] > 0


@pytest.mark.asyncio
async def test_unhealthy_llm_falls_back_to_retrieve(settings, db, vectors, pipeline):
    await pipeline.ingest_text(NOTE_A, source_type="upload", title="Rust notes")
    chat = FakeChat(healthy=False, answer="should not be used")
    client, _ = await _client(settings, db=db, vectors=vectors, pipeline=pipeline, chat=chat)
    async with client:
        resp = await client.get(
            "/search",
            params={"q": NOTE_A, "mode": "auto"},
            headers={"Authorization": "Bearer test-token"},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["mode"] == "retrieve"
    assert body["answer"] is None
    assert body["citations"]
    assert chat.complete_calls == 0


@pytest.mark.asyncio
async def test_llm_error_falls_back_to_retrieve(settings, db, vectors, pipeline):
    await pipeline.ingest_text(NOTE_A, source_type="upload", title="Rust notes")
    chat = FakeChat(fail=True)
    client, _ = await _client(settings, db=db, vectors=vectors, pipeline=pipeline, chat=chat)
    async with client:
        resp = await client.get(
            "/search",
            params={"q": NOTE_A, "mode": "rag"},
            headers={"Authorization": "Bearer test-token"},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["mode"] == "retrieve"
    assert body["answer"] is None
    assert body["citations"][0]["title"] == "Rust notes"


@pytest.mark.asyncio
async def test_answer_without_markers_still_attaches_hits(settings, db, vectors, pipeline):
    await pipeline.ingest_text(NOTE_A, source_type="upload", title="Rust notes")
    chat = FakeChat(answer="Ownership is exclusive.")
    client, _ = await _client(settings, db=db, vectors=vectors, pipeline=pipeline, chat=chat)
    async with client:
        resp = await client.get(
            "/search",
            params={"q": NOTE_A, "mode": "rag"},
            headers={"Authorization": "Bearer test-token"},
        )
    body = resp.json()
    assert body["mode"] == "rag"
    assert body["citations"]
    assert body["citations"][0]["title"] == "Rust notes"


@pytest.mark.asyncio
async def test_offline_provider_stays_retrieve_only(settings, db, vectors, pipeline):
    await pipeline.ingest_text(NOTE_A, source_type="upload", title="Rust notes")
    client, _ = await _client(
        settings,
        db=db,
        vectors=vectors,
        pipeline=pipeline,
        chat=OfflineProvider(),
    )
    async with client:
        resp = await client.get(
            "/search",
            params={"q": NOTE_A, "mode": "auto"},
            headers={"Authorization": "Bearer test-token"},
        )
    body = resp.json()
    assert body["mode"] == "retrieve"
    assert body["answer"] is None
    assert body["citations"][0]["title"] == "Rust notes"
