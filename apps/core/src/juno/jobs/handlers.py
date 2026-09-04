"""Job bodies. Digest pushes reuse /digest grouping; resurfacing stays #89."""

from __future__ import annotations

import logging
from typing import Any

from juno.bot.services import digest_since, format_digest, recent_captures

logger = logging.getLogger("juno.jobs")


async def push_scheduled_digest(app: Any, window: str) -> int:
    """Push a /digest-style summary to allowlisted chats. Respects /pause."""
    from juno.jobs.scheduler import send_allowlisted_push

    if app is None:
        return 0
    if bool(getattr(app.state, "capture_paused", False)):
        logger.info("digest %s skipped — capture paused", window)
        return 0
    db = getattr(app.state, "db", None)
    settings = getattr(app.state, "settings", None)
    if db is None or settings is None:
        logger.warning("digest %s skipped — runtime not attached", window)
        return 0
    ptb = getattr(app.state, "ptb", None)
    bot = getattr(ptb, "bot", None) if ptb is not None else None
    rows = await recent_captures(db, since=digest_since(window))
    body = format_digest(rows, window)
    title = "Morning digest" if window == "today" else "Weekly digest"
    return await send_allowlisted_push(
        bot,
        settings,
        f"{title}\n{body}",
        is_paused=lambda: bool(getattr(app.state, "capture_paused", False)),
    )


async def digest_daily(app: Any) -> None:
    sent = await push_scheduled_digest(app, "today")
    logger.info("digest_daily sent to %s chat(s)", sent)


async def digest_weekly(app: Any) -> None:
    sent = await push_scheduled_digest(app, "week")
    logger.info("digest_weekly sent to %s chat(s)", sent)


async def resurfacing(app: Any) -> None:
    from juno.jobs.resurface import apply_resurface_candidates, find_resurface_candidates

    db = getattr(app.state, "db", None) if app is not None else None
    vectors = getattr(app.state, "vectors", None) if app is not None else None
    if db is None:
        logger.info("resurfacing skipped — database not attached")
        return
    candidates = await find_resurface_candidates(db, vectors)
    stats = await apply_resurface_candidates(app, candidates)
    logger.info("resurfacing pushed=%s queued=%s", stats["pushed"], stats["queued"])
