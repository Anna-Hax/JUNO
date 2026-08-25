"""Minimal Telegram command handlers (M1 skeleton)."""

from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

from juno.bot.review import review_callback, review_cmd
from juno.config import Settings, get_settings

__all__ = [
    "help_cmd",
    "review_callback",
    "review_cmd",
    "start_cmd",
    "text_query",
]


def _settings(context: ContextTypes.DEFAULT_TYPE) -> Settings:
    stored = context.application.bot_data.get("settings")
    if stored is not None:
        return stored
    services = context.application.bot_data.get("juno")
    if services is not None and getattr(services, "settings", None) is not None:
        return services.settings
    return get_settings()


def _allowed(user_id: int | None, context: ContextTypes.DEFAULT_TYPE) -> bool:
    allow = _settings(context).allowed_user_id_set()
    if not allow:
        # Empty allowlist = reject everyone until configured (security default)
        return False
    return user_id is not None and user_id in allow


async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not _allowed(update.effective_user.id, context):
        return
    if update.message is None:
        return
    await update.message.reply_text(
        "Juno online. Ask a question, or /help for commands.\n"
        "Local-first: I only run while this PC is on."
    )


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not _allowed(update.effective_user.id, context):
        return
    if update.message is None:
        return
    await update.message.reply_text(
        "Commands:\n"
        "/start — hello\n"
        "/help — this message\n"
        "/digest today|week — (coming)\n"
        "/pause /resume — (coming)\n"
        "/status — (coming)\n"
        "/review — HITL queue (Approve / Reject / Skip)\n"
        "Or send a link/doc/text to capture."
    )


async def text_query(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not _allowed(update.effective_user.id, context):
        return
    if update.message is None:
        return
    text = (update.message.text or "").strip()
    if not text:
        return
    await update.message.reply_text(
        f"Received ({len(text)} chars). RAG answers land in M1 — "
        "schema and retrieve are being wired."
    )
