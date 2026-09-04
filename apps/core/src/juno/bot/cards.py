"""Telegram /cards — due SRS prompts. Generation of new cards stays HITL."""

from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from juno.bot.services import BOT_DATA_KEY, BotServices, user_allowed
from juno.config import Settings, get_settings
from juno.drafts.flashcards import (
    format_card_prompt,
    format_card_reveal,
    next_due_card,
    queue_highlight_flashcards,
    review_card,
)
from juno.models import Flashcard

_GRADES = {"again": "Again", "good": "Good"}


def _services(context: ContextTypes.DEFAULT_TYPE) -> BotServices | None:
    raw = context.application.bot_data.get(BOT_DATA_KEY)
    return raw if isinstance(raw, BotServices) else None


def _settings(context: ContextTypes.DEFAULT_TYPE) -> Settings:
    stored = context.application.bot_data.get("settings")
    if stored is not None:
        return stored
    svc = _services(context)
    return svc.settings if svc is not None else get_settings()


def _allowed(user_id: int | None, context: ContextTypes.DEFAULT_TYPE) -> bool:
    return user_allowed(user_id, _settings(context))


def cards_keyboard(card_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Again", callback_data=f"srs:{card_id}:again"),
                InlineKeyboardButton("Good", callback_data=f"srs:{card_id}:good"),
            ]
        ]
    )


def parse_srs_callback(data: str) -> tuple[int, str] | None:
    parts = data.split(":")
    if len(parts) != 3 or parts[0] != "srs":
        return None
    try:
        card_id = int(parts[1])
    except ValueError:
        return None
    grade = parts[2]
    if grade not in _GRADES:
        return None
    return card_id, grade


def _paused(context: ContextTypes.DEFAULT_TYPE) -> bool:
    svc = _services(context)
    app = svc.app if svc is not None else None
    if app is None:
        return False
    return bool(getattr(app.state, "capture_paused", False))


def _card_text(card: Flashcard) -> str:
    return f"{format_card_prompt(card)}\n\n{format_card_reveal(card)}"


async def cards_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not _allowed(update.effective_user.id, context):
        return
    if update.message is None:
        return
    svc = _services(context)
    if svc is None or svc.db is None:
        await update.message.reply_text("Cards unavailable (database not attached).")
        return
    queued = await queue_highlight_flashcards(svc.db, paused=_paused(context))
    due = await next_due_card(svc.db)
    prefix = f"Queued {len(queued)} flashcard draft(s) for /review.\n\n" if queued else ""
    if due is None:
        msg = prefix + "No flashcards due."
        if _paused(context):
            msg += " Capture is paused, so no new drafts were generated."
        await update.message.reply_text(msg)
        return
    await update.message.reply_text(
        prefix + _card_text(due),
        reply_markup=cards_keyboard(due.id),
    )


async def cards_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if query is None:
        return
    if not update.effective_user or not _allowed(update.effective_user.id, context):
        await query.answer()
        return
    parsed = parse_srs_callback(query.data or "")
    if parsed is None:
        await query.answer("Unknown button")
        return
    card_id, grade = parsed
    svc = _services(context)
    if svc is None or svc.db is None:
        await query.answer("Cards unavailable.")
        return
    try:
        graded = await review_card(svc.db, card_id, grade)
    except LookupError:
        await query.answer("That card is gone.")
        await query.edit_message_text("Flashcard not found.")
        return
    await query.answer()
    nxt = await next_due_card(svc.db)
    verb = _GRADES[grade]
    text = f"{verb} on flashcard #{graded.id}."
    if nxt is None:
        await query.edit_message_text(text + "\n\nNo more cards due.")
        return
    await query.edit_message_text(
        text + f"\n\nNext:\n{_card_text(nxt)}",
        reply_markup=cards_keyboard(nxt.id),
    )
