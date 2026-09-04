"""Telegram HITL surface: /review plus Approve / Reject / Skip inline buttons."""

from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from juno.bot.services import BOT_DATA_KEY, BotServices, user_allowed
from juno.config import Settings, get_settings
from juno.hitl.queue import Decision, ReviewCard, ReviewQueue

_VERBS = {"approve": "Approved", "reject": "Rejected", "skip": "Skipped"}


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


def review_queue_from_context(context: ContextTypes.DEFAULT_TYPE) -> ReviewQueue | None:
    queue = context.application.bot_data.get("review")
    if isinstance(queue, ReviewQueue):
        return queue
    svc = _services(context)
    if svc is not None and svc.db is not None:
        queue = ReviewQueue(svc.db, vectors=svc.vectors)
        context.application.bot_data["review"] = queue
        return queue
    return None


def review_keyboard(item_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Approve", callback_data=f"rev:{item_id}:approve"),
                InlineKeyboardButton("Reject", callback_data=f"rev:{item_id}:reject"),
                InlineKeyboardButton("Skip", callback_data=f"rev:{item_id}:skip"),
            ]
        ]
    )


def parse_review_callback(data: str) -> tuple[int, Decision] | None:
    parts = data.split(":")
    if len(parts) != 3 or parts[0] != "rev":
        return None
    try:
        item_id = int(parts[1])
    except ValueError:
        return None
    action = parts[2]
    if action not in {"approve", "reject", "skip"}:
        return None
    return item_id, action  # type: ignore[return-value]


def _card_text(card: ReviewCard) -> str:
    return card.summary()


async def review_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not _allowed(update.effective_user.id, context):
        return
    if update.message is None:
        return
    queue = review_queue_from_context(context)
    if queue is None:
        await update.message.reply_text("Review queue is not available.")
        return
    card = await queue.next_open()
    if card is None:
        await update.message.reply_text("Review queue empty.")
        return
    await update.message.reply_text(_card_text(card), reply_markup=review_keyboard(card.id))


async def review_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if query is None:
        return
    if not update.effective_user or not _allowed(update.effective_user.id, context):
        await query.answer()
        return
    parsed = parse_review_callback(query.data or "")
    if parsed is None:
        await query.answer("Unknown button")
        return
    item_id, decision = parsed
    queue = review_queue_from_context(context)
    if queue is None:
        await query.answer("Review queue is not available.")
        return
    try:
        result = await queue.decide(item_id, decision)
    except LookupError:
        await query.answer("That review item is gone.")
        await query.edit_message_text("Review item not found.")
        return

    await query.answer()
    verb = _VERBS[decision]
    if result.already_decided:
        text = f"Review #{item_id} was already {result.card.decision}."
    else:
        text = f"{verb} review #{item_id}."
        if result.card.kind == "merge" and decision == "approve":
            text += " Merge is now committed."
        elif result.card.kind == "merge" and decision == "reject":
            text += " Merge was not applied."
        elif result.card.kind == "draft" and decision == "approve":
            text += " Draft confirmed; it was not published."
        elif result.card.kind == "draft" and decision == "reject":
            text += " Draft discarded; it was not published."
        elif result.card.kind == "prune" and decision == "approve":
            n = len(result.card.payload.get("capture_ids") or [])
            text += f" Archived {n} capture(s); this is not a wipe."
        elif result.card.kind == "prune" and decision == "reject":
            text += " Captures left in the graph."
        elif decision == "skip":
            text += " Left in the queue."

    nxt = result.next_card
    if nxt is None:
        await query.edit_message_text(text + "\n\nReview queue empty.")
        return
    if nxt.id == item_id and decision == "skip":
        await query.edit_message_text(
            text + "\n\nNo other items — this one stays in the queue.",
            reply_markup=review_keyboard(item_id),
        )
        return
    await query.edit_message_text(
        text + f"\n\nNext:\n{_card_text(nxt)}",
        reply_markup=review_keyboard(nxt.id),
    )
