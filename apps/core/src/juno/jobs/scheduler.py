"""APScheduler on the shared uvicorn/PTB asyncio loop (ADR-01 / ADR-07)."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from juno.config import Settings

logger = logging.getLogger("juno.jobs")

SMOKE_JOB_ID = "spike_s4_smoke"
SMOKE_TEXT = "Juno jobs smoke: AsyncIOScheduler fired on the shared serve loop."


def create_scheduler(timezone: str = "UTC") -> AsyncIOScheduler:
    """Build an AsyncIOScheduler bound to the currently running event loop on start()."""
    tz = ZoneInfo(timezone)
    return AsyncIOScheduler(timezone=tz, event_loop=None)


async def send_allowlisted_push(
    bot: Any,
    settings: Settings,
    text: str,
    *,
    is_paused: Callable[[], bool] | None = None,
) -> int:
    """Send `text` to every allowlisted Telegram user. Skip when paused or empty allowlist."""
    if is_paused is not None and is_paused():
        logger.info("jobs push skipped — capture paused")
        return 0
    if bot is None:
        logger.info("jobs push skipped — bot not attached")
        return 0
    ids = settings.allowed_user_id_set()
    if not ids:
        logger.warning("jobs push skipped — empty ALLOWED_TELEGRAM_USER_IDS")
        return 0
    sent = 0
    for uid in sorted(ids):
        try:
            await bot.send_message(chat_id=uid, text=text)
        except Exception:
            logger.exception("jobs push failed for chat_id=%s", uid)
            continue
        sent += 1
    logger.info("jobs push sent to %s allowlisted chat(s)", sent)
    return sent


def register_smoke_job(
    scheduler: AsyncIOScheduler,
    *,
    coro_factory: Callable[[], Awaitable[None]],
    delay_seconds: float = 2.0,
) -> None:
    """One-shot date job so Spike S4 can prove a fire on this loop without cron."""
    run_date = datetime.now(UTC) + timedelta(seconds=delay_seconds)
    scheduler.add_job(
        coro_factory,
        "date",
        run_date=run_date,
        id=SMOKE_JOB_ID,
        replace_existing=True,
        misfire_grace_time=60,
    )


def start_jobs(app: Any) -> AsyncIOScheduler | None:
    """Start AsyncIOScheduler on the serve loop. Optional one-shot Telegram smoke push."""
    settings: Settings = app.state.settings
    if not settings.juno_jobs_enabled:
        logger.info("jobs scheduler disabled (JUNO_JOBS_ENABLED=false)")
        app.state.scheduler = None
        return None

    scheduler = create_scheduler(settings.juno_jobs_timezone)
    scheduler.start()
    app.state.scheduler = scheduler
    logger.info(
        "jobs scheduler started (AsyncIOScheduler tz=%s)",
        settings.juno_jobs_timezone,
    )

    if settings.juno_jobs_smoke:
        ptb = getattr(app.state, "ptb", None)
        bot = getattr(ptb, "bot", None) if ptb is not None else None

        async def smoke() -> None:
            await send_allowlisted_push(
                bot,
                settings,
                SMOKE_TEXT,
                is_paused=lambda: bool(getattr(app.state, "capture_paused", False)),
            )

        register_smoke_job(scheduler, coro_factory=smoke)
        logger.info("jobs smoke job registered (%s)", SMOKE_JOB_ID)

    return scheduler


def stop_jobs(app: Any) -> None:
    scheduler = getattr(app.state, "scheduler", None)
    if scheduler is None:
        return
    if scheduler.running:
        scheduler.shutdown(wait=False)
    app.state.scheduler = None
    logger.info("jobs scheduler stopped")
