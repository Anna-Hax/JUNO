"""Telegram command and message handlers."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from telegram import Update
from telegram.ext import ContextTypes

from juno.bot.services import (
    BOT_DATA_KEY,
    BotServices,
    all_module_health,
    answer_user_query,
    clip,
    digest_since,
    format_capture_ack,
    format_digest,
    format_status,
    is_forwarded,
    recent_captures,
    single_http_url,
    user_allowed,
)
from juno.config import Settings, get_settings

logger = logging.getLogger("juno.bot")

HELP_TEXT = (
    "Commands:\n"
    "/start — hello\n"
    "/help — this message\n"
    "/digest today|week — recent captures\n"
    "/pause — stop all ingest\n"
    "/resume — resume ingest (processes inbox backlog)\n"
    "/status — capture + module health\n"
    "/review — HITL queue (coming)\n"
    "Ask a question to search the graph.\n"
    "Forward a message, send a link, or attach a doc to capture."
)


def _services(context: ContextTypes.DEFAULT_TYPE) -> BotServices | None:
    raw = context.bot_data.get(BOT_DATA_KEY)
    return raw if isinstance(raw, BotServices) else None


def _settings(context: ContextTypes.DEFAULT_TYPE) -> Settings:
    svc = _services(context)
    return svc.settings if svc is not None else get_settings()


def _authorized(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    user = update.effective_user
    uid = user.id if user else None
    return user_allowed(uid, _settings(context))


async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not _authorized(update, context):
        return
    await update.message.reply_text(
        "Juno online. Ask a question, or /help for commands.\n"
        "Local-first: I only run while this PC is on."
    )


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not _authorized(update, context):
        return
    await update.message.reply_text(HELP_TEXT)


async def digest_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not _authorized(update, context):
        return
    args = [a.lower() for a in (context.args or [])]
    window = args[0] if args else "today"
    if window not in {"today", "week"}:
        await update.message.reply_text("Usage: /digest today|week")
        return
    svc = _services(context)
    if svc is None or svc.db is None:
        await update.message.reply_text("Digest unavailable (database not attached).")
        return
    rows = await recent_captures(svc.db, since=digest_since(window))
    await update.message.reply_text(format_digest(rows, window))


async def pause_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not _authorized(update, context):
        return
    svc = _services(context)
    if svc is None:
        await update.message.reply_text("Pause unavailable (runtime not attached).")
        return
    await svc.set_paused(True)
    await update.message.reply_text(
        "Capture paused. Inbox, API /ingest, and Telegram capture are stopped."
    )


async def resume_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not _authorized(update, context):
        return
    svc = _services(context)
    if svc is None:
        await update.message.reply_text("Resume unavailable (runtime not attached).")
        return
    await svc.set_paused(False)
    await update.message.reply_text("Capture resumed. Inbox backlog (if any) is being processed.")


async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not _authorized(update, context):
        return
    svc = _services(context)
    if svc is None:
        await update.message.reply_text("Status unavailable (runtime not attached).")
        return
    settings = svc.settings
    embedder = getattr(svc.app.state, "embedder", None) if svc.app is not None else None
    chat = getattr(svc.app.state, "chat", None) if svc.app is not None else None
    llm_healthy = bool(svc.app is not None and getattr(svc.app.state, "llm_healthy", False))
    if chat is not None:
        try:
            llm_healthy = bool(await chat.healthy(timeout=1.5))
        except TypeError:
            llm_healthy = bool(await chat.healthy())
        if svc.app is not None:
            svc.app.state.llm_healthy = llm_healthy
    chroma_count = 0
    chroma_collection = getattr(svc.vectors, "collection_name", None)
    if svc.vectors is not None and hasattr(svc.vectors, "count"):
        chroma_count = await asyncio.to_thread(svc.vectors.count)
    health: list = []
    if svc.db is not None:
        health = await all_module_health(svc.db)
    await update.message.reply_text(
        format_status(
            paused=svc.is_paused(),
            llm_healthy=llm_healthy,
            llm_provider=getattr(chat, "name", None) or settings.llm_provider,
            llm_model=getattr(chat, "model", None) or settings.llm_model,
            embedding_model=getattr(embedder, "model_id", settings.embedding_model),
            embedding_backend=getattr(embedder, "backend", settings.embedding_backend),
            chroma_collection=chroma_collection,
            chroma_count=chroma_count,
            health=health,
            api_host=settings.juno_api_host,
            api_port=settings.juno_api_port,
        )
    )


async def text_msg(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not _authorized(update, context):
        return
    text = (update.message.text or "").strip()
    if not text:
        return
    if is_forwarded(update.message) or single_http_url(text):
        await _capture_text(update, context, text)
        return
    await _query_text(update, context, text)


async def document_msg(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not _authorized(update, context):
        return
    svc = _services(context)
    if svc is None or svc.pipeline is None:
        await update.message.reply_text("Capture unavailable (ingest pipeline not attached).")
        return
    if svc.is_paused():
        await update.message.reply_text("Capture is paused. /resume to ingest again.")
        return
    doc = update.message.document
    if doc is None:
        return
    dest = _telegram_tmp(svc, doc.file_name or "upload.bin", doc.file_unique_id)
    try:
        file = await doc.get_file()
        await file.download_to_drive(custom_path=dest)
        result = await svc.pipeline.ingest_path(dest, source_type="telegram")
    except Exception as exc:  # noqa: BLE001
        logger.exception("telegram document ingest failed")
        await update.message.reply_text(clip(f"Capture failed: {exc}"))
        return
    finally:
        dest.unlink(missing_ok=True)
    await update.message.reply_text(format_capture_ack(result))


async def _capture_text(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str) -> None:
    assert update.message is not None
    svc = _services(context)
    if svc is None or svc.pipeline is None:
        await update.message.reply_text("Capture unavailable (ingest pipeline not attached).")
        return
    if svc.is_paused():
        await update.message.reply_text("Capture is paused. /resume to ingest again.")
        return
    url = single_http_url(text)
    try:
        if url:
            result = await svc.pipeline.ingest_url(url, source_type="telegram")
        else:
            title = None
            if is_forwarded(update.message):
                title = (update.message.forward_sender_name or None)
            result = await svc.pipeline.ingest_text(
                text,
                source_type="telegram",
                title=title,
            )
    except Exception as exc:  # noqa: BLE001
        logger.exception("telegram text capture failed")
        await update.message.reply_text(clip(f"Capture failed: {exc}"))
        return
    await update.message.reply_text(format_capture_ack(result))


async def _query_text(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str) -> None:
    assert update.message is not None
    svc = _services(context)
    if svc is None:
        await update.message.reply_text(
            f"Received ({len(text)} chars). Search is not attached in this runtime."
        )
        return
    try:
        reply = await answer_user_query(svc, text)
    except Exception:  # noqa: BLE001
        logger.exception("telegram query failed")
        await update.message.reply_text("Search failed. Try again after checking /status.")
        return
    await update.message.reply_text(reply)


def _telegram_tmp(svc: BotServices, filename: str, unique_id: str) -> Path:
    folder = svc.settings.juno_data_dir / "telegram"
    folder.mkdir(parents=True, exist_ok=True)
    suffix = Path(filename).suffix or ".bin"
    safe_id = "".join(ch for ch in unique_id if ch.isalnum() or ch in "-_") or "file"
    return folder / f"{safe_id}{suffix}"
