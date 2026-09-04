"""Job bodies. Digest pushes reuse /digest grouping; resurfacing stays #89."""

from __future__ import annotations

import logging
from typing import Any

from juno.bot.services import digest_since, format_digest, recent_captures
from juno.jobs.health import record_jobs_health

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
    await _run_digest_job(app, job_id="digest_daily", window="today")


async def digest_weekly(app: Any) -> None:
    await _run_digest_job(app, job_id="digest_weekly", window="week")


async def _run_digest_job(app: Any, *, job_id: str, window: str) -> None:
    db = getattr(app.state, "db", None) if app is not None else None
    try:
        if app is not None and bool(getattr(app.state, "capture_paused", False)):
            logger.info("%s skipped — capture paused", job_id)
            await record_jobs_health(db, detail=f"{job_id} skipped (paused)", ok=True)
            return
        sent = await push_scheduled_digest(app, window)
        logger.info("%s sent to %s chat(s)", job_id, sent)
        await record_jobs_health(db, detail=f"{job_id} sent={sent}", ok=True)
    except Exception as exc:  # noqa: BLE001
        logger.exception("%s failed", job_id)
        await record_jobs_health(db, detail=job_id, ok=False, error=str(exc))
        raise


async def resurfacing(app: Any) -> None:
    from juno.jobs.resurface import apply_resurface_candidates, find_resurface_candidates

    db = getattr(app.state, "db", None) if app is not None else None
    vectors = getattr(app.state, "vectors", None) if app is not None else None
    if db is None:
        logger.info("resurfacing skipped — database not attached")
        return
    try:
        if app is not None and bool(getattr(app.state, "capture_paused", False)):
            await record_jobs_health(db, detail="resurfacing skipped (paused)", ok=True)
            return
        candidates = await find_resurface_candidates(db, vectors)
        stats = await apply_resurface_candidates(app, candidates)
        logger.info("resurfacing pushed=%s queued=%s", stats["pushed"], stats["queued"])
        await record_jobs_health(
            db,
            detail=f"resurfacing pushed={stats['pushed']} queued={stats['queued']}",
            ok=True,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("resurfacing failed")
        await record_jobs_health(db, detail="resurfacing", ok=False, error=str(exc))
        raise
