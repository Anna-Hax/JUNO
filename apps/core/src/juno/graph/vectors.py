"""Persistent Chroma wrapper — one collection per embedding model.

Blocking Chroma I/O should go through the async helpers (`asyncio.to_thread`)
when called from the serve loop (ADR-01).
"""

from __future__ import annotations

import asyncio
import hashlib
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import chromadb
from chromadb.config import Settings as ChromaSettings

from juno.config import Settings
from juno.llm.embedder import Embedder

_UNSAFE = re.compile(r"[^a-zA-Z0-9._-]+")
_REPEAT_SEP = re.compile(r"[-._]{2,}")


def collection_name_for_model(model_id: str) -> str:
    """Map an embedding model id to a valid Chroma collection name (3–63 chars)."""
    slug = _UNSAFE.sub("-", (model_id or "").strip())
    slug = _REPEAT_SEP.sub("-", slug).strip("-._")
    if not slug:
        slug = "model"
    if slug[0].isdigit():
        slug = f"m-{slug}"
    name = f"juno-{slug}"
    if len(name) > 63:
        digest = hashlib.sha1(model_id.encode("utf-8")).hexdigest()[:8]
        name = f"{name[:54].rstrip('-._')}-{digest}"
    if not name[-1].isalnum():
        name = f"{name.rstrip('-._')}x"
    if len(name) < 3:
        name = f"{name}xxx"[:3]
    return name


def _clean_metadata(meta: Mapping[str, Any] | None) -> dict[str, str | int | float | bool]:
    if not meta:
        return {"source": "juno"}
    cleaned: dict[str, str | int | float | bool] = {}
    for key, value in meta.items():
        if value is None:
            continue
        if isinstance(value, (str, int, float, bool)):
            cleaned[key] = value
        else:
            cleaned[key] = str(value)
    return cleaned or {"source": "juno"}


@dataclass(frozen=True)
class VectorHit:
    id: str
    text: str | None
    metadata: dict[str, Any]
    distance: float | None


class VectorStore:
    """Disk-backed Chroma client scoped to the current embedding model."""

    def __init__(self, settings: Settings, embedder: Embedder) -> None:
        settings.chroma_path.mkdir(parents=True, exist_ok=True)
        self._embedder = embedder
        self.collection_name = collection_name_for_model(embedder.model_id)
        self._client = chromadb.PersistentClient(
            path=str(settings.chroma_path.resolve()),
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        self._collection = self._client.get_or_create_collection(
            name=self.collection_name,
            metadata={
                "hnsw:space": "cosine",
                "embedding_model": embedder.model_id,
                "embedding_dimensions": embedder.dimensions,
            },
            embedding_function=None,
        )

    def upsert(
        self,
        *,
        ids: Sequence[str],
        texts: Sequence[str],
        metadatas: Sequence[Mapping[str, Any]] | None = None,
    ) -> None:
        if len(ids) != len(texts):
            raise ValueError("ids and texts must be the same length")
        if not ids:
            return
        if metadatas is not None and len(metadatas) != len(ids):
            raise ValueError("metadatas must be the same length as ids")
        embeddings = self._embedder.embed(list(texts))
        metas = [
            _clean_metadata(metadatas[i] if metadatas is not None else None)
            for i in range(len(ids))
        ]
        self._collection.upsert(
            ids=list(ids),
            documents=list(texts),
            embeddings=embeddings,
            metadatas=metas,
        )

    def query(self, text: str, *, n_results: int = 8) -> list[VectorHit]:
        if n_results < 1:
            raise ValueError("n_results must be >= 1")
        total = self._collection.count()
        if total == 0:
            return []
        k = min(n_results, total)
        [embedding] = self._embedder.embed([text])
        raw = self._collection.query(
            query_embeddings=[embedding],
            n_results=k,
            include=["documents", "metadatas", "distances"],
        )
        ids = (raw.get("ids") or [[]])[0]
        documents = (raw.get("documents") or [[]])[0]
        metadatas = (raw.get("metadatas") or [[]])[0]
        distances = (raw.get("distances") or [[]])[0]
        hits: list[VectorHit] = []
        for i, item_id in enumerate(ids):
            doc = documents[i] if i < len(documents) else None
            meta = metadatas[i] if i < len(metadatas) else None
            dist = distances[i] if i < len(distances) else None
            hits.append(
                VectorHit(
                    id=item_id,
                    text=doc,
                    metadata=dict(meta or {}),
                    distance=dist,
                )
            )
        return hits

    def delete(self, ids: Sequence[str]) -> None:
        if ids:
            self._collection.delete(ids=list(ids))

    def count(self) -> int:
        return self._collection.count()

    async def upsert_async(
        self,
        *,
        ids: Sequence[str],
        texts: Sequence[str],
        metadatas: Sequence[Mapping[str, Any]] | None = None,
    ) -> None:
        await asyncio.to_thread(self.upsert, ids=ids, texts=texts, metadatas=metadatas)

    async def query_async(self, text: str, *, n_results: int = 8) -> list[VectorHit]:
        return await asyncio.to_thread(self.query, text, n_results=n_results)
