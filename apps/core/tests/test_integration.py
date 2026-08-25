"""End-to-end happy paths: ingest → retrieve/RAG → HITL review (mocked LLM)."""

from __future__ import annotations

import httpx
import pytest

from juno.api import create_app
from juno.graph.db import Database
from juno.graph.vectors import VectorStore
from juno.hitl.queue import EDGE_COMMITTED, EDGE_PENDING, ReviewQueue
from juno.ingest.pipeline import IngestPipeline
from juno.llm.embedder import StubEmbedder
from juno.models import Edge

RUST_NOTE = (
    "Juno integration marker alpha-42. "
    "Ownership in Rust means each value has a single owner at a time."
)
GARDEN_NOTE = "Garden soil pH and tomatoes — unrelated to compilers."


class FakeChat:
    def __init__(self, *, healthy: bool = True, answer: str = "") -> None:
        self._healthy = healthy
        self._answer = answer
        self.complete_calls = 0

    async def healthy(self, *, timeout: float = 3.0) -> bool:
        return self._healthy

    async def complete(self, system: str, messages: list[dict[str, str]], **kwargs):  # noqa: ANN001
        self.complete_calls += 1
        assert "Sources:" in messages[0]["content"]
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


@pytest.fixture
def review(db):
    return ReviewQueue(db)


async def _api_client(settings, *, db, vectors, pipeline, chat=None):
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


@pytest.mark.asyncio
async def test_happy_path_ingest_retrieve_review(settings, db, vectors, pipeline, review):
    """CI happy path: capture → vector search → pending merge → approve."""
    ingest = await pipeline.ingest_text(RUST_NOTE, source_type="upload", title="Rust notes")
    assert ingest.status == "committed"
    assert ingest.capture_id is not None
    assert vectors.count() == 1

    client, _ = await _api_client(settings, db=db, vectors=vectors, pipeline=pipeline)
    async with client:
        search = await client.get(
            "/search",
            params={"q": RUST_NOTE, "mode": "retrieve"},
            headers={"Authorization": "Bearer test-token"},
        )
    assert search.status_code == 200
    body = search.json()
    assert body["mode"] == "retrieve"
    assert body["results"]
    assert body["results"][0]["capture_id"] == ingest.capture_id
    assert "alpha-42" in body["results"][0]["text"]
    assert body["citations"]

    card = await review.propose_merge(
        from_name="Rust ownership",
        to_name="Rust",
        confidence=0.55,
        reason="integration test cluster",
    )
    assert card.status == "pending"
    edge_id = int(card.payload["edge_id"])
    assert await _edge_status(db, edge_id) == EDGE_PENDING

    result = await review.decide(card.id, "approve")
    assert result.applied is True
    assert result.card.decision == "approve"
    assert await _edge_status(db, edge_id) == EDGE_COMMITTED


@pytest.mark.asyncio
async def test_happy_path_ingest_rag_then_review_with_mock_llm(
    settings, db, vectors, pipeline, review
):
    await pipeline.ingest_text(RUST_NOTE, source_type="upload", title="Rust notes")
    await pipeline.ingest_text(GARDEN_NOTE, source_type="upload", title="Garden")

    chat = FakeChat(answer="Each value has a single owner [1].")
    client, _ = await _api_client(
        settings,
        db=db,
        vectors=vectors,
        pipeline=pipeline,
        chat=chat,
    )
    async with client:
        search = await client.get(
            "/search",
            params={"q": RUST_NOTE, "mode": "auto"},
            headers={"Authorization": "Bearer test-token"},
        )
    assert search.status_code == 200
    body = search.json()
    assert body["mode"] == "rag"
    assert body["answer"] == "Each value has a single owner [1]."
    assert body["citations"]
    assert chat.complete_calls == 1

    card = await review.propose_merge(from_name="Rust", to_name="Ownership", confidence=0.7)
    skip = await review.decide(card.id, "skip")
    assert skip.applied is False
    assert skip.card.status == "skipped"
    assert await _edge_status(db, int(card.payload["edge_id"])) == EDGE_PENDING

    approve = await review.decide(card.id, "approve")
    assert approve.applied is True
    assert await _edge_status(db, int(card.payload["edge_id"])) == EDGE_COMMITTED


@pytest.mark.asyncio
async def test_ingest_via_api_then_search(settings, db, vectors, pipeline):
    client, _ = await _api_client(settings, db=db, vectors=vectors, pipeline=pipeline)
    async with client:
        ingest = await client.post(
            "/ingest",
            json={"source_type": "upload", "text": RUST_NOTE, "title": "via api"},
            headers={"Authorization": "Bearer test-token"},
        )
        search = await client.get(
            "/search",
            params={"q": RUST_NOTE, "mode": "retrieve"},
            headers={"Authorization": "Bearer test-token"},
        )
    assert ingest.status_code == 200
    assert ingest.json()["status"] == "committed"
    assert search.status_code == 200
    assert search.json()["results"]
    assert search.json()["results"][0]["title"] == "via api"


async def _edge_status(db: Database, edge_id: int) -> str | None:
    async def load(session):
        edge = await session.get(Edge, edge_id)
        return None if edge is None else edge.status

    return await db.read(load)
