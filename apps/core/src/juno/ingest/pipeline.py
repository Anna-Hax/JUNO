"""Ingest pipeline: extract → chunk → SQLite (write queue) → optional vectors."""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from juno.graph.db import Database
from juno.ingest.chunking import chunk_text
from juno.ingest.extractors import Extracted, ExtractError, extract_path, extract_url
from juno.models import Capture, Chunk, ModuleHealth

logger = logging.getLogger("juno.ingest.pipeline")


def _parse_visited_at(value: Any) -> datetime | None:
    """Parse extension/client ISO timestamp for captured_at."""
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


class VectorSink(Protocol):
    """Subset of VectorStore used by ingest (ADR-04). Optional until #13 lands."""

    async def upsert_async(
        self,
        *,
        ids: Sequence[str],
        texts: Sequence[str],
        metadatas: Sequence[Mapping[str, Any]] | None = None,
    ) -> None: ...


@dataclass(frozen=True)
class IngestResult:
    accepted: bool
    source_type: str
    status: str
    capture_id: int | None
    chunk_count: int = 0
    error_reason: str | None = None
    title: str | None = None
    uri: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "accepted": self.accepted,
            "source_type": self.source_type,
            "status": self.status,
            "capture_id": self.capture_id,
            "chunk_count": self.chunk_count,
            "error_reason": self.error_reason,
            "title": self.title,
            "uri": self.uri,
        }


class IngestPipeline:
    def __init__(self, db: Database, vectors: VectorSink | None = None) -> None:
        self.db = db
        self.vectors = vectors

    async def ingest_path(self, path: Path, *, source_type: str = "upload") -> IngestResult:
        uri = path.resolve().as_uri() if path.exists() else str(path)
        try:
            extracted = await extract_path(path)
        except ExtractError as exc:
            return await self._fail(
                source_type,
                reason=exc.reason,
                uri=uri,
                title=path.name,
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("extract failed for %s", path)
            return await self._fail(
                source_type,
                reason=f"extract failed: {exc}",
                uri=uri,
                title=path.name,
            )
        return await self._commit(extracted, source_type=extracted.source_type or source_type)

    async def ingest_url(
        self,
        url: str,
        *,
        source_type: str = "url",
        client: Any = None,
    ) -> IngestResult:
        try:
            extracted = await extract_url(url, client=client)
        except ExtractError as exc:
            return await self._fail(source_type, reason=exc.reason, uri=url)
        except Exception as exc:  # noqa: BLE001
            logger.exception("url extract failed for %s", url)
            return await self._fail(source_type, reason=f"extract failed: {exc}", uri=url)
        return await self._commit(extracted, source_type=source_type)

    async def ingest_text(
        self,
        text: str,
        *,
        source_type: str = "api",
        uri: str | None = None,
        title: str | None = None,
        raw: dict[str, Any] | None = None,
        captured_at: datetime | None = None,
    ) -> IngestResult:
        extracted = Extracted(
            text=text or "",
            title=title,
            uri=uri,
            source_type=source_type,
            raw=raw or {"extractor": "inline"},
        )
        return await self._commit(extracted, source_type=source_type, captured_at=captured_at)

    async def ingest_payload(self, payload: dict[str, Any]) -> IngestResult:
        source_type = str(payload.get("source_type") or "api")
        path_val = payload.get("path")
        uri = payload.get("uri")
        text = payload.get("text")
        title = payload.get("title")
        raw = payload.get("raw_json")
        if not isinstance(raw, dict):
            raw = None
        visited_at = _parse_visited_at(payload.get("visited_at"))
        if visited_at is None and raw is not None:
            visited_at = _parse_visited_at(raw.get("visited_at"))

        if path_val:
            return await self.ingest_path(Path(str(path_val)), source_type=source_type)
        if isinstance(uri, str) and uri.startswith(("http://", "https://")) and not text:
            kind = source_type if source_type not in {"api", ""} else "url"
            return await self.ingest_url(uri, source_type=kind)
        browser_raw = raw or {}
        if source_type == "browser":
            browser_raw = {
                **browser_raw,
                "visited_at": (visited_at or datetime.now(UTC)).isoformat(),
                "uri": uri,
                "title": title,
            }
        return await self.ingest_text(
            text=str(text) if text is not None else "",
            source_type=source_type,
            uri=str(uri) if uri else None,
            title=str(title) if title else None,
            raw=browser_raw if source_type == "browser" else raw,
            captured_at=visited_at,
        )

    async def _commit(
        self,
        extracted: Extracted,
        *,
        source_type: str,
        captured_at: datetime | None = None,
    ) -> IngestResult:
        pieces = chunk_text(extracted.text or "")

        async def write(session: AsyncSession) -> tuple[int, list[tuple[str, str]]]:
            capture = Capture(
                source_type=source_type,
                uri=extracted.uri,
                title=extracted.title,
                text=extracted.text or None,
                raw_json=extracted.raw or None,
                status="committed",
            )
            if captured_at is not None:
                capture.captured_at = captured_at
            session.add(capture)
            await session.flush()
            stored: list[tuple[str, str]] = []
            for ordinal, piece in enumerate(pieces):
                chroma_id = f"c{capture.id}-n{ordinal}"
                session.add(
                    Chunk(
                        capture_id=capture.id,
                        ordinal=ordinal,
                        text=piece,
                        chroma_id=chroma_id,
                    )
                )
                stored.append((chroma_id, piece))
            await _touch_health(session, ok=True)
            return capture.id, stored

        capture_id, stored = await self.db.write(write)
        await self._upsert_vectors(capture_id, source_type, stored)
        return IngestResult(
            accepted=True,
            source_type=source_type,
            status="committed",
            capture_id=capture_id,
            chunk_count=len(stored),
            title=extracted.title,
            uri=extracted.uri,
        )

    async def _fail(
        self,
        source_type: str,
        *,
        reason: str,
        uri: str | None = None,
        title: str | None = None,
    ) -> IngestResult:
        async def write(session: AsyncSession) -> int:
            capture = Capture(
                source_type=source_type,
                uri=uri,
                title=title,
                text=None,
                status="failed",
                error_reason=reason,
            )
            session.add(capture)
            await session.flush()
            await _touch_health(session, ok=False, error=reason)
            return capture.id

        capture_id = await self.db.write(write)
        return IngestResult(
            accepted=True,
            source_type=source_type,
            status="failed",
            capture_id=capture_id,
            chunk_count=0,
            error_reason=reason,
            title=title,
            uri=uri,
        )

    async def _upsert_vectors(
        self,
        capture_id: int,
        source_type: str,
        stored: list[tuple[str, str]],
    ) -> None:
        if self.vectors is None or not stored:
            return
        try:
            await self.vectors.upsert_async(
                ids=[item[0] for item in stored],
                texts=[item[1] for item in stored],
                metadatas=[
                    {"capture_id": capture_id, "source_type": source_type, "ordinal": i}
                    for i, _ in enumerate(stored)
                ],
            )
        except Exception:  # noqa: BLE001
            logger.exception("vector upsert failed for capture %s", capture_id)


async def _touch_health(session: AsyncSession, *, ok: bool, error: str | None = None) -> None:
    row = await session.get(ModuleHealth, "ingest")
    if row is None:
        row = ModuleHealth(module="ingest")
        session.add(row)
    now = datetime.now(UTC)
    if ok:
        row.last_success_at = now
        row.last_error = None
        row.detail = "ok"
    else:
        row.last_error_at = now
        row.last_error = (error or "unknown")[:2000]
        row.detail = "error"
