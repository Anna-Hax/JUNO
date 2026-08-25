from __future__ import annotations

import pytest

from juno.graph.vectors import VectorStore, collection_name_for_model
from juno.llm.embedder import StubEmbedder


def test_collection_name_for_model_sanitizes():
    assert collection_name_for_model("all-MiniLM-L6-v2") == "juno-all-MiniLM-L6-v2"
    assert collection_name_for_model("sentence-transformers/all-MiniLM-L6-v2") == (
        "juno-sentence-transformers-all-MiniLM-L6-v2"
    )
    name = collection_name_for_model("x" * 80)
    assert 3 <= len(name) <= 63
    assert name[0].isalnum()
    assert name[-1].isalnum()


@pytest.mark.asyncio
async def test_vector_store_persists_across_restart(settings):
    embedder = StubEmbedder()
    store = VectorStore(settings, embedder)
    store.upsert(
        ids=["chunk-1"],
        texts=["rust ownership and borrowing"],
        metadatas=[{"capture_id": 1}],
    )
    assert store.count() == 1
    assert (settings.chroma_path / "chroma.sqlite3").exists() or any(settings.chroma_path.iterdir())

    reopened = VectorStore(settings, embedder)
    assert reopened.collection_name == store.collection_name
    assert reopened.count() == 1
    hits = reopened.query("rust borrowing")
    assert hits
    assert hits[0].id == "chunk-1"
    assert hits[0].metadata["capture_id"] == 1

    async_hits = await reopened.query_async("ownership")
    assert async_hits[0].id == "chunk-1"


def test_vector_store_isolates_collections_per_model(settings):
    a = VectorStore(settings, StubEmbedder(model_id="stub-hash-v1"))
    b = VectorStore(settings, StubEmbedder(model_id="stub-hash-v2"))
    assert a.collection_name != b.collection_name
    a.upsert(ids=["a1"], texts=["alpha topic"])
    assert a.count() == 1
    assert b.count() == 0
    b.upsert(ids=["b1"], texts=["beta topic"])
    assert a.count() == 1
    assert b.count() == 1


def test_status_reports_chroma_collection(settings):
    from fastapi.testclient import TestClient

    from juno.api import create_app

    embedder = StubEmbedder()
    vectors = VectorStore(settings, embedder)
    vectors.upsert(ids=["c1"], texts=["hello graph"])
    app = create_app(settings, embedder=embedder, vectors=vectors)
    client = TestClient(app)
    resp = client.get("/status", headers={"Authorization": "Bearer test-token"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["chroma_collection"] == vectors.collection_name
    assert body["chroma_count"] == 1
    assert body["embedding_model"] == "stub-hash-v1"
    assert body["embedding_backend"] == "stub"
    assert body["embedding_dimensions"] == 64
    assert body["embedding_fallback"] is False
    assert body["llm_healthy"] is False
    assert "llm_provider" in body
