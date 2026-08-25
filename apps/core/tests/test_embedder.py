from __future__ import annotations

import sys
from types import ModuleType

import pytest
from sqlalchemy import select

from juno.graph.db import Database
from juno.llm.embedder import StubEmbedder, create_embedder
from juno.models import AppSetting
from juno.runtime import persist_embedder_settings


def test_stub_embedder_batch():
    emb = StubEmbedder()
    vecs = emb.embed(["alpha", "beta", "gamma"])
    assert len(vecs) == 3
    assert all(len(v) == 64 for v in vecs)
    assert vecs[0] != vecs[1]
    assert emb.embed(["alpha"])[0] == vecs[0]


def test_stub_embedder_empty_batch():
    assert StubEmbedder().embed([]) == []


def test_create_embedder_unknown_backend():
    with pytest.raises(ValueError, match="Unknown embedding backend"):
        create_embedder("mystery", "x")


def test_minilm_path_batch_embed(monkeypatch):
    """sentence_transformers factory + batch encode without downloading MiniLM."""

    class FakeVectors:
        def __init__(self, rows: list[list[float]]) -> None:
            self._rows = rows

        def tolist(self) -> list[list[float]]:
            return self._rows

    class FakeSentenceTransformer:
        def __init__(self, model_id: str) -> None:
            assert model_id == "all-MiniLM-L6-v2"
            self.model_id = model_id

        def get_sentence_embedding_dimension(self) -> int:
            return 384

        def encode(self, texts: list[str], normalize_embeddings: bool = True) -> FakeVectors:
            assert normalize_embeddings is True
            return FakeVectors([[0.01 * (i + 1)] * 384 for i, _ in enumerate(texts)])

    fake = ModuleType("sentence_transformers")
    fake.SentenceTransformer = FakeSentenceTransformer  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "sentence_transformers", fake)

    emb = create_embedder("sentence_transformers", "all-MiniLM-L6-v2")
    assert emb.backend == "sentence_transformers"
    assert emb.model_id == "all-MiniLM-L6-v2"
    assert emb.dimensions == 384
    assert emb.embed([]) == []
    vecs = emb.embed(["rust ownership", "borrowing"])
    assert len(vecs) == 2
    assert len(vecs[0]) == 384
    assert vecs[0] != vecs[1]


def test_minilm_missing_extra_has_install_hint(monkeypatch):
    monkeypatch.setitem(sys.modules, "sentence_transformers", None)
    with pytest.raises(ImportError, match="uv sync --extra embeddings"):
        create_embedder("sentence_transformers", "all-MiniLM-L6-v2")


@pytest.mark.asyncio
async def test_persist_embedder_model_id_in_settings(settings):
    db = Database(settings)
    await db.create_all()
    await persist_embedder_settings(db, StubEmbedder())

    async def fetch(session):
        result = await session.execute(select(AppSetting))
        return {row.key: row.value for row in result.scalars()}

    rows = await db.read(fetch)
    assert rows["embedding_model"] == "stub-hash-v1"
    assert rows["embedding_backend"] == "stub"
    assert rows["embedding_dimensions"] == "64"
    await db.dispose()


def test_status_reports_actual_embedder_not_settings_backend(settings):
    from fastapi.testclient import TestClient

    from juno.api import create_app

    # Requested MiniLM, but serve fell back to stub — /status must not lie.
    settings = settings.model_copy(update={"embedding_backend": "sentence_transformers"})
    embedder = StubEmbedder()
    app = create_app(settings, embedder=embedder)
    client = TestClient(app)
    body = client.get("/status", headers={"Authorization": "Bearer test-token"}).json()
    assert body["embedding_backend"] == "stub"
    assert body["embedding_model"] == "stub-hash-v1"
    assert body["embedding_dimensions"] == 64
    assert body["embedding_fallback"] is True
