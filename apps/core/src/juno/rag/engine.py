"""Query VectorStore, join SQLite captures, optionally generate a sourced answer."""

from __future__ import annotations

import logging
import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from juno.graph.db import Database
from juno.graph.vectors import VectorHit
from juno.models import Capture, Chunk

logger = logging.getLogger("juno.rag")

DEFAULT_K = 8
MAX_SOURCE_CHARS = 1200
_CITE_RE = re.compile(r"\[(\d+)\]")
ERROR_QUERY_HINTS = (
    "error",
    "traceback",
    "exception",
    "failed",
    "panic:",
    "cannot use",
    "database is locked",
    "have i seen this",
)
TEMPORAL_QUERY_HINTS = (
    "evolved",
    "over time",
    "how has my",
    "timeline",
    "used to think",
    "changed my",
    "history of",
)

RAG_SYSTEM = (
    "You are Juno, a personal knowledge assistant. Answer using ONLY the numbered "
    "sources. Cite sources as [1], [2], matching those numbers. If the sources do "
    "not contain the answer, say you don't know. Do not invent facts or citations."
)


@dataclass(frozen=True)
class SourcedHit:
    chroma_id: str
    text: str
    score: float
    capture_id: int | None = None
    chunk_id: int | None = None
    ordinal: int | None = None
    title: str | None = None
    uri: str | None = None
    source_type: str | None = None
    captured_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        captured = None
        if self.captured_at is not None:
            captured = self.captured_at.isoformat()
        return {
            "chroma_id": self.chroma_id,
            "capture_id": self.capture_id,
            "chunk_id": self.chunk_id,
            "ordinal": self.ordinal,
            "title": self.title,
            "uri": self.uri,
            "source_type": self.source_type,
            "captured_at": captured,
            "text": self.text,
            "score": round(self.score, 4),
        }


@dataclass(frozen=True)
class SearchOutcome:
    query: str
    mode: str
    results: list[SourcedHit]
    confidence: float
    answer: str | None = None
    citations: list[SourcedHit] | None = None

    def to_dict(self) -> dict[str, Any]:
        cites = self.citations if self.citations is not None else self.results
        return {
            "query": self.query,
            "mode": self.mode,
            "answer": self.answer,
            "confidence": round(self.confidence, 4),
            "results": [hit.to_dict() for hit in self.results],
            "citations": [hit.to_dict() for hit in cites],
        }


def similarity_from_distance(distance: float | None) -> float:
    """Chroma cosine space stores distance = 1 - cosine similarity."""
    if distance is None:
        return 0.0
    return max(0.0, min(1.0, 1.0 - float(distance)))


def _as_int(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _confidence(hits: Sequence[SourcedHit]) -> float:
    if not hits:
        return 0.0
    return max(hit.score for hit in hits)


async def retrieve(
    query: str,
    *,
    vectors: Any,
    db: Database | None,
    n_results: int = DEFAULT_K,
) -> list[SourcedHit]:
    """Vector search then join hits to `chunks` / `captures` (ADR-04)."""
    q = (query or "").strip()
    if not q or vectors is None or n_results < 1:
        return []
    hits: list[VectorHit] = await vectors.query_async(q, n_results=n_results)
    if not hits:
        return []
    by_chroma = await _load_chunks(db, [hit.id for hit in hits])
    sourced: list[SourcedHit] = []
    for hit in hits:
        chunk, capture = by_chroma.get(hit.id, (None, None))
        if capture is not None and capture.status == "archived":
            continue
        meta = hit.metadata or {}
        text = (chunk.text if chunk is not None else None) or hit.text or ""
        sourced.append(
            SourcedHit(
                chroma_id=hit.id,
                text=text,
                score=similarity_from_distance(hit.distance),
                capture_id=(capture.id if capture is not None else _as_int(meta.get("capture_id"))),
                chunk_id=chunk.id if chunk is not None else None,
                ordinal=(chunk.ordinal if chunk is not None else _as_int(meta.get("ordinal"))),
                title=capture.title if capture is not None else None,
                uri=capture.uri if capture is not None else None,
                source_type=(
                    capture.source_type
                    if capture is not None
                    else (str(meta["source_type"]) if meta.get("source_type") else None)
                ),
                captured_at=capture.captured_at if capture is not None else None,
            )
        )
    return sourced


async def _load_chunks(
    db: Database | None, chroma_ids: Sequence[str]
) -> dict[str, tuple[Chunk | None, Capture | None]]:
    if db is None or not chroma_ids:
        return {}

    async def fetch(
        session: AsyncSession,
    ) -> dict[str, tuple[Chunk | None, Capture | None]]:
        result = await session.execute(
            select(Chunk, Capture)
            .join(Capture, Chunk.capture_id == Capture.id)
            .where(Chunk.chroma_id.in_(list(chroma_ids)))
        )
        mapped: dict[str, tuple[Chunk | None, Capture | None]] = {}
        for chunk, capture in result.all():
            if chunk.chroma_id:
                mapped[chunk.chroma_id] = (chunk, capture)
        return mapped

    return await db.read(fetch)


async def _chat_is_healthy(chat: Any) -> bool:
    if chat is None:
        return False
    probe = getattr(chat, "healthy", None)
    if probe is None:
        return False
    try:
        return bool(await probe(timeout=1.5))
    except TypeError:
        try:
            return bool(await probe())
        except Exception:  # noqa: BLE001
            return False
    except Exception:  # noqa: BLE001
        logger.exception("LLM health probe failed")
        return False


def _format_sources(hits: Sequence[SourcedHit]) -> str:
    lines: list[str] = []
    for i, hit in enumerate(hits, start=1):
        label = hit.title or hit.uri or hit.chroma_id
        body = hit.text.strip()
        if len(body) > MAX_SOURCE_CHARS:
            body = body[: MAX_SOURCE_CHARS - 1] + "…"
        lines.append(f"[{i}] {label}\n{body}")
    return "\n\n".join(lines)


def _cited_hits(answer: str, hits: Sequence[SourcedHit]) -> list[SourcedHit]:
    cited: list[SourcedHit] = []
    seen: set[int] = set()
    for match in _CITE_RE.finditer(answer):
        idx = int(match.group(1))
        if idx in seen or idx < 1 or idx > len(hits):
            continue
        seen.add(idx)
        cited.append(hits[idx - 1])
    return cited


async def search(
    query: str,
    *,
    vectors: Any,
    db: Database | None,
    chat: Any = None,
    n_results: int = DEFAULT_K,
    mode: str = "auto",
) -> SearchOutcome:
    """Retrieve hits; generate a sourced answer when an LLM is healthy."""
    q = (query or "").strip()
    requested = (mode or "auto").strip().lower()
    n = n_results
    if requested in {"auto", "temporal"} and looks_like_temporal_query(q):
        n = max(n_results, 12)
    hits = await retrieve(q, vectors=vectors, db=db, n_results=n)
    retrieve_confidence = _confidence(hits)

    if requested == "temporal" or (requested == "auto" and looks_like_temporal_query(q) and hits):
        ordered = _sorted_by_captured_at(hits)
        return SearchOutcome(
            query=q,
            mode="temporal",
            results=ordered,
            confidence=retrieve_confidence,
            answer=None,
            citations=ordered,
        )

    want_rag = requested in {"auto", "rag"} and bool(hits)

    if requested == "retrieve" or not want_rag:
        return SearchOutcome(
            query=q,
            mode="retrieve",
            results=hits,
            confidence=retrieve_confidence,
            answer=None,
            citations=hits,
        )

    if not await _chat_is_healthy(chat):
        return SearchOutcome(
            query=q,
            mode="retrieve",
            results=hits,
            confidence=retrieve_confidence,
            answer=None,
            citations=hits,
        )

    try:
        answer = (
            await chat.complete(
                RAG_SYSTEM,
                [
                    {
                        "role": "user",
                        "content": f"Question: {q}\n\nSources:\n{_format_sources(hits)}",
                    }
                ],
            )
        ).strip()
    except Exception:  # noqa: BLE001
        logger.exception("RAG generate failed; falling back to retrieve-only")
        return SearchOutcome(
            query=q,
            mode="retrieve",
            results=hits,
            confidence=retrieve_confidence,
            answer=None,
            citations=hits,
        )

    if not answer:
        return SearchOutcome(
            query=q,
            mode="retrieve",
            results=hits,
            confidence=retrieve_confidence,
            answer=None,
            citations=hits,
        )

    citations = _cited_hits(answer, hits) or list(hits)
    rag_confidence = _confidence(citations)
    return SearchOutcome(
        query=q,
        mode="rag",
        results=hits,
        confidence=rag_confidence,
        answer=answer,
        citations=citations,
    )


def looks_like_error_query(query: str) -> bool:
    q = (query or "").casefold()
    return any(hint in q for hint in ERROR_QUERY_HINTS)


def looks_like_temporal_query(query: str) -> bool:
    q = (query or "").casefold()
    return any(hint in q for hint in TEMPORAL_QUERY_HINTS)


def _sorted_by_captured_at(hits: Sequence[SourcedHit]) -> list[SourcedHit]:
    def key(hit: SourcedHit) -> datetime:
        when = hit.captured_at
        if when is None:
            return datetime.min.replace(tzinfo=UTC)
        if when.tzinfo is None:
            return when.replace(tzinfo=UTC)
        return when

    return sorted(hits, key=key)


async def match_past_errors(
    query: str,
    *,
    vectors: Any,
    db: Database | None,
    chat: Any = None,
    review: Any = None,
    n_results: int = DEFAULT_K,
) -> SearchOutcome:
    """Semantic 'have I seen this error before?' over IDE chats/errors (#69).

    Uses retrieve-only when the LLM is unhealthy (same as ``search``).
    High-scoring IDE hits are queued for HITL before reuse as canonical (#68).
    """
    outcome = await search(
        query,
        vectors=vectors,
        db=db,
        chat=chat,
        n_results=n_results,
        mode="auto",
    )
    ide = [hit for hit in outcome.results if hit.source_type == "ide"]
    others = [hit for hit in outcome.results if hit.source_type != "ide"]
    ordered = ide + others
    confidence = _confidence(ordered if ordered else outcome.results)
    if review is not None and ide:
        top = ide[0]
        if top.score >= 0.45:
            try:
                await review.propose_error_match(
                    new_title=(query or "")[:120],
                    past_title=top.title or top.uri or "past IDE capture",
                    confidence=float(top.score),
                    past_capture_id=top.capture_id,
                    reason="Similar IDE error/chat — confirm same root cause before reuse.",
                )
            except Exception:  # noqa: BLE001
                logger.exception("failed to enqueue error_match review")
    return SearchOutcome(
        query=outcome.query,
        mode=outcome.mode,
        results=ordered or list(outcome.results),
        confidence=confidence,
        answer=outcome.answer,
        citations=ordered or list(outcome.citations or outcome.results),
    )
