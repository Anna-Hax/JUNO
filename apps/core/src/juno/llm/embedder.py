"""Embedding backends — stub for CI, sentence-transformers for local use."""

from __future__ import annotations

import hashlib
import struct
from abc import ABC, abstractmethod


class Embedder(ABC):
    backend: str
    model_id: str
    dimensions: int

    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError


class StubEmbedder(Embedder):
    """Deterministic hash-based vectors for tests/CI (no torch download)."""

    backend = "stub"

    def __init__(self, model_id: str = "stub-hash-v1", dimensions: int = 64) -> None:
        self.model_id = model_id
        self.dimensions = dimensions

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._one(t) for t in texts]

    def _one(self, text: str) -> list[float]:
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        vals: list[float] = []
        seed = digest
        while len(vals) < self.dimensions:
            for i in range(0, len(seed), 4):
                if len(vals) >= self.dimensions:
                    break
                chunk = seed[i : i + 4]
                if len(chunk) < 4:
                    chunk = chunk.ljust(4, b"\0")
                (n,) = struct.unpack(">I", chunk)
                vals.append((n / 0xFFFFFFFF) * 2.0 - 1.0)
            seed = hashlib.sha256(seed).digest()
        # L2 normalize
        norm = sum(v * v for v in vals) ** 0.5 or 1.0
        return [v / norm for v in vals]


class SentenceTransformerEmbedder(Embedder):
    backend = "sentence_transformers"

    def __init__(self, model_id: str = "all-MiniLM-L6-v2") -> None:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise ImportError(
                "sentence-transformers is not installed. "
                "From apps/core run: uv sync --extra embeddings"
            ) from exc

        self.model_id = model_id
        self._model = SentenceTransformer(model_id)
        self.dimensions = int(self._model.get_sentence_embedding_dimension())

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        vectors = self._model.encode(texts, normalize_embeddings=True)
        rows = vectors.tolist() if hasattr(vectors, "tolist") else [list(v) for v in vectors]
        if rows and isinstance(rows[0], (int, float)):
            return [list(rows)]
        return [list(row) for row in rows]


def create_embedder(backend: str, model_id: str) -> Embedder:
    if backend == "stub":
        return StubEmbedder()
    if backend == "sentence_transformers":
        return SentenceTransformerEmbedder(model_id=model_id)
    raise ValueError(f"Unknown embedding backend: {backend}")
