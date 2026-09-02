"""Bot helpers: allowlist, pause persistence, digest/status/query formatting."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlparse

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from juno.config import Settings
from juno.graph.db import Database
from juno.ingest.pipeline import IngestResult
from juno.models import AppSetting, Capture, ModuleHealth
from juno.rag.engine import looks_like_error_query, match_past_errors
from juno.rag.engine import search as rag_search

BOT_DATA_KEY = "juno"
CAPTURE_PAUSED_KEY = "capture_paused"
TELEGRAM_LIMIT = 4000
_URL_ONLY = re.compile(r"^https?://\S+$", re.IGNORECASE)


@dataclass
class BotServices:
    settings: Settings
    db: Database | None = None
    pipeline: Any = None
    vectors: Any = None
    app: Any = None

    def is_paused(self) -> bool:
        app = self.app
        return bool(app is not None and getattr(app.state, "capture_paused", False))

    async def set_paused(self, paused: bool) -> None:
        if self.app is not None:
            self.app.state.capture_paused = paused
        if self.db is not None:
            await persist_capture_paused(self.db, paused)
        if not paused and self.app is not None:
            watcher = getattr(self.app.state, "inbox_watcher", None)
            if watcher is not None:
                await watcher.scan_existing()


def user_allowed(user_id: int | None, settings: Settings) -> bool:
    allow = settings.allowed_user_id_set()
    if not allow:
        return False
    return user_id is not None and user_id in allow


def single_http_url(text: str) -> str | None:
    stripped = (text or "").strip()
    if not stripped or "\n" in stripped or "\r" in stripped:
        return None
    if _URL_ONLY.match(stripped):
        return stripped
    return None


def is_forwarded(message: Any) -> bool:
    return bool(
        getattr(message, "forward_origin", None)
        or getattr(message, "forward_date", None)
        or getattr(message, "forward_from", None)
        or getattr(message, "forward_from_chat", None)
        or getattr(message, "forward_sender_name", None)
    )


def clip(text: str, limit: int = TELEGRAM_LIMIT) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def format_retrieve_reply(query: str, hits: list[Any]) -> str:
    if not hits:
        return (
            "Nothing in the graph matched that yet. "
            "Forward a note or drop a file in inbox/, then ask again."
        )
    q = " ".join(query.split())
    if len(q) > 80:
        q = q[:79].rstrip() + "…"
    lines = [f'Retrieve-only for "{q}" ({len(hits)} hit{"s" if len(hits) != 1 else ""}):']
    for i, hit in enumerate(hits, start=1):
        lines.append(_format_vector_hit(i, hit))
        snippet = _snippet(getattr(hit, "text", None))
        if snippet:
            lines.append(f"   {snippet}")
    return clip("\n".join(lines))


def format_search_outcome(outcome: Any) -> str:
    results = list(getattr(outcome, "results", None) or [])
    if not results:
        return (
            "Nothing in the graph matched that yet. "
            "Forward a note or drop a file in inbox/, then ask again."
        )
    citations = list(getattr(outcome, "citations", None) or results)
    confidence = float(getattr(outcome, "confidence", 0.0) or 0.0)
    answer = getattr(outcome, "answer", None)
    mode = getattr(outcome, "mode", "retrieve")
    lines: list[str] = []
    if mode == "rag" and answer:
        lines.append(str(answer).strip())
        lines.append("")
        lines.append(f"Confidence: {confidence:.0%}")
        lines.append("Sources:")
        for i, hit in enumerate(citations, start=1):
            lines.append(_format_sourced_hit(i, hit))
    else:
        lines.append(f"Retrieve-only (confidence {confidence:.0%}):")
        for i, hit in enumerate(results, start=1):
            lines.append(_format_sourced_hit(i, hit))
            snippet = _snippet(getattr(hit, "text", None))
            if snippet:
                lines.append(f"   {snippet}")
    return clip("\n".join(lines))


async def answer_user_query(svc: BotServices, text: str) -> str:
    if svc.vectors is None:
        return f"Received ({len(text)} chars). Search is not attached in this runtime."
    chat = getattr(svc.app.state, "chat", None) if svc.app is not None else None
    review = None
    if svc.db is not None and looks_like_error_query(text):
        from juno.hitl.queue import ReviewQueue

        review = ReviewQueue(svc.db)
        outcome = await match_past_errors(
            text,
            vectors=svc.vectors,
            db=svc.db,
            chat=chat,
            review=review,
            n_results=5,
        )
    else:
        outcome = await rag_search(
            text,
            vectors=svc.vectors,
            db=svc.db,
            chat=chat,
            n_results=5,
            mode="auto",
        )
    reply = format_search_outcome(outcome)
    if svc.db is None:
        return reply
    browser_hits = [
        hit for hit in outcome.results if getattr(hit, "source_type", None) == "browser"
    ]
    ide_hits = [hit for hit in outcome.results if getattr(hit, "source_type", None) == "ide"]
    extra: list[str] = []
    if ide_hits:
        related = await related_captures(
            svc.db, hits=ide_hits, source_types=("browser", "upload"), limit=3
        )
        if related:
            extra.append("")
            extra.append("You also read or uploaded notes on:")
            for row in related:
                label = row.title or row.uri or f"capture #{row.id}"
                extra.append(f"• #{row.id} [{row.source_type}] {label}")
    if browser_hits:
        related = await related_upload_captures(svc.db, browser_hits=browser_hits)
        if related:
            extra.append("")
            extra.append("You also uploaded notes on:")
            for row in related:
                label = row.title or row.uri or f"capture #{row.id}"
                extra.append(f"• #{row.id} {label}")
    if not extra:
        return reply
    return clip(reply + "\n".join(extra))


def format_capture_ack(result: IngestResult) -> str:
    if result.status == "failed":
        reason = result.error_reason or "unknown error"
        cid = f" #{result.capture_id}" if result.capture_id else ""
        return clip(f"Capture failed{cid}: {reason}")
    title = result.title or result.uri or result.source_type
    return (
        f"Captured #{result.capture_id} ({result.source_type}, "
        f"{result.chunk_count} chunk{'s' if result.chunk_count != 1 else ''}): {title}"
    )


def _ide_kind(row: Capture) -> str:
    raw = row.raw_json if isinstance(row.raw_json, dict) else {}
    kind = str(raw.get("kind") or "")
    if kind == "cursor_error":
        return "error"
    return "chat"


def format_digest(captures: list[Capture], window: str) -> str:
    label = "today" if window == "today" else "this week"
    if not captures:
        return f"No captures {label}."
    browser = [row for row in captures if row.source_type == "browser"]
    ide = [row for row in captures if row.source_type == "ide"]
    other = [row for row in captures if row.source_type not in {"browser", "ide"}]
    ide_chat = [row for row in ide if _ide_kind(row) == "chat"]
    ide_err = [row for row in ide if _ide_kind(row) == "error"]
    lines = [f"Digest {label} ({len(captures)}):"]
    if browser:
        lines.append(f"Browser reading ({len(browser)}):")
        lines.extend(_digest_lines(browser))
    if ide_chat:
        lines.append(f"IDE chats ({len(ide_chat)}):")
        lines.extend(_digest_lines(ide_chat))
    if ide_err:
        lines.append(f"IDE errors ({len(ide_err)}):")
        lines.extend(_digest_lines(ide_err))
    if other:
        if browser or ide:
            lines.append(f"Uploads / other ({len(other)}):")
        lines.extend(_digest_lines(other))
    return clip("\n".join(lines))


def _digest_lines(rows: list[Capture]) -> list[str]:
    lines: list[str] = []
    for row in rows:
        when = _fmt_dt(row.captured_at)
        title = row.title or row.uri or (row.text or "")[:60] or "(no text)"
        title = " ".join(str(title).split())
        if len(title) > 80:
            title = title[:79].rstrip() + "…"
        lines.append(f"• #{row.id} [{row.source_type}/{row.status}] {when} — {title}")
    return lines


def format_status(
    *,
    paused: bool,
    llm_healthy: bool,
    embedding_model: str,
    chroma_collection: str | None,
    chroma_count: int,
    health: list[ModuleHealth],
    api_host: str,
    api_port: int,
    llm_provider: str | None = None,
    llm_model: str | None = None,
    embedding_backend: str | None = None,
) -> str:
    llm = "healthy" if llm_healthy else "offline (retrieve-only)"
    if llm_provider:
        ident = f"{llm_provider}/{llm_model}" if llm_model else llm_provider
        llm = f"{llm} ({ident})"
    embedder_line = embedding_model
    if embedding_backend:
        embedder_line = f"{embedding_model} [{embedding_backend}]"
    lines = [
        "Juno status",
        f"Capture: {'paused' if paused else 'running'}",
        f"LLM: {llm}",
        f"Embedder: {embedder_line}",
        f"Vectors: {chroma_collection or 'n/a'} ({chroma_count} chunks)",
        f"API: http://{api_host}:{api_port}",
    ]
    if health:
        lines.append("Modules:")
        for row in health:
            last_ok = _fmt_dt(row.last_success_at) if row.last_success_at else "never"
            extra = row.detail or "ok"
            if row.last_error:
                extra = f"error: {row.last_error[:120]}"
            lines.append(f"• {row.module}: last ok {last_ok} ({extra})")
    else:
        lines.append("Modules: none recorded yet")
    return clip("\n".join(lines))


def digest_since(window: str, *, now: datetime | None = None) -> datetime:
    now = now or datetime.now(UTC)
    if window == "week":
        return now - timedelta(days=7)
    return now - timedelta(days=1)


async def load_capture_paused(db: Database) -> bool:
    async def fn(session: AsyncSession) -> bool:
        row = await session.get(AppSetting, CAPTURE_PAUSED_KEY)
        if row is None:
            return False
        return row.value.strip().lower() in {"1", "true", "yes", "on"}

    return await db.read(fn)


async def persist_capture_paused(db: Database, paused: bool) -> None:
    value = "true" if paused else "false"

    async def fn(session: AsyncSession) -> None:
        row = await session.get(AppSetting, CAPTURE_PAUSED_KEY)
        if row is None:
            session.add(AppSetting(key=CAPTURE_PAUSED_KEY, value=value))
        else:
            row.value = value

    await db.write(fn)


async def recent_captures(db: Database, *, since: datetime, limit: int = 20) -> list[Capture]:
    async def fn(session: AsyncSession) -> list[Capture]:
        result = await session.execute(
            select(Capture)
            .where(Capture.captured_at >= since)
            .order_by(Capture.captured_at.desc())
            .limit(limit)
        )
        return list(result.scalars())

    return await db.read(fn)


async def related_captures(
    db: Database,
    *,
    hits: list[Any],
    source_types: tuple[str, ...],
    limit: int = 3,
) -> list[Capture]:
    """Find committed captures of the given source types matching hit titles/text."""
    titles: set[str] = set()
    hosts: set[str] = set()
    for hit in hits:
        title = (getattr(hit, "title", None) or "").strip()
        if title:
            titles.add(title[:80])
        text = (getattr(hit, "text", None) or "").strip()
        if text:
            titles.add(text[:80])
        uri = getattr(hit, "uri", None) or ""
        if uri:
            host = urlparse(uri).netloc.lower()
            if host:
                hosts.add(host)
    if not titles and not hosts:
        return []

    async def fn(session: AsyncSession) -> list[Capture]:
        clauses = []
        for title in list(titles)[:4]:
            for word in re.findall(r"[A-Za-z]{4,}", title)[:6]:
                clauses.append(Capture.title.ilike(f"%{word}%"))
                clauses.append(Capture.text.ilike(f"%{word}%"))
        for host in list(hosts)[:3]:
            clauses.append(Capture.uri.ilike(f"%{host}%"))
        if not clauses:
            return []
        result = await session.execute(
            select(Capture)
            .where(Capture.source_type.in_(source_types))
            .where(Capture.status == "committed")
            .where(or_(*clauses))
            .order_by(Capture.captured_at.desc())
            .limit(limit)
        )
        return list(result.scalars())

    return await db.read(fn)


async def related_upload_captures(
    db: Database,
    *,
    browser_hits: list[Any],
    limit: int = 3,
) -> list[Capture]:
    """Cross-reference browser hits with upload/inbox captures (#51)."""
    return await related_captures(
        db,
        hits=browser_hits,
        source_types=("upload", "telegram", "url", "api"),
        limit=limit,
    )


async def all_module_health(db: Database) -> list[ModuleHealth]:
    async def fn(session: AsyncSession) -> list[ModuleHealth]:
        result = await session.execute(select(ModuleHealth).order_by(ModuleHealth.module))
        return list(result.scalars())

    return await db.read(fn)


def _similarity(distance: float | None) -> str:
    if distance is None:
        return "score ?"
    sim = max(0.0, min(1.0, 1.0 - float(distance)))
    return f"{sim:.0%}"


def _fmt_dt(value: datetime | None) -> str:
    if value is None:
        return "unknown"
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).strftime("%Y-%m-%d %H:%M UTC")


def _snippet(text: str | None) -> str:
    snippet = (text or "").strip().replace("\n", " ")
    if len(snippet) > 240:
        return snippet[:239].rstrip() + "…"
    return snippet


def _format_vector_hit(i: int, hit: Any) -> str:
    meta = getattr(hit, "metadata", None) or {}
    source = meta.get("source_type") or "capture"
    capture_id = meta.get("capture_id")
    label = f"{source} #{capture_id}" if capture_id is not None else str(source)
    return f"{i}. {label} ({_similarity(getattr(hit, 'distance', None))})"


def _format_sourced_hit(i: int, hit: Any) -> str:
    source = getattr(hit, "source_type", None) or "capture"
    capture_id = getattr(hit, "capture_id", None)
    title = getattr(hit, "title", None) or getattr(hit, "uri", None) or ""
    label = f"{source} #{capture_id}" if capture_id is not None else str(source)
    if title:
        label = f"{label} — {title}"
    score = getattr(hit, "score", None)
    if score is not None:
        score_s = f"{float(score):.0%}"
    else:
        score_s = _similarity(getattr(hit, "distance", None))
    return f"{i}. {label} ({score_s})"
