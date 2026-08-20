"""Minimal Telegram command handlers (M1 skeleton)."""

from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

from juno.config import get_settings


def _allowed(user_id: int | None) -> bool:
    settings = get_settings()
    allow = settings.allowed_user_id_set()
    if not allow:
        # Empty allowlist = reject everyone until configured (security default)
        return False
    return user_id is not None and user_id in allow


async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not _allowed(update.effective_user.id):
        return
    await update.message.reply_text(
        "Juno online. Ask a question, or /help for commands.\n"
        "Local-first: I only run while this PC is on."
    )


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not _allowed(update.effective_user.id):
        return
    await update.message.reply_text(
        "Commands:\n"
        "/start — hello\n"
        "/help — this message\n"
        "/digest today|week — (coming)\n"
        "/pause /resume — (coming)\n"
        "/status — (coming)\n"
        "/review — HITL queue (coming)\n"
        "Or send a link/doc/text to capture."
    )


async def text_query(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not _allowed(update.effective_user.id):
        return
    text = (update.message.text or "").strip()
    if not text:
        return
    await update.message.reply_text(
        f"Received ({len(text)} chars). RAG answers land in M1 — "
        "schema and retrieve are being wired."
    )
