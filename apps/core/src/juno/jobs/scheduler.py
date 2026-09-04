"""APScheduler on the shared uvicorn/PTB asyncio loop (ADR-01 / ADR-07)."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from juno.config import Settings
from juno.jobs.handlers import digest_daily, digest_weekly, polish, resurfacing
from juno.jobs.registry import (
    DIGEST_DAILY_JOB_ID,
    DIGEST_WEEKLY_JOB_ID,
    POLISH_JOB_ID,
    RESURFACING_JOB_ID,
    JobSpec,
    apply_enabled_overrides,
    builtin_job_specs,
)

logger = logging.getLogger("juno.jobs")

SMOKE_JOB_ID = "spike_s4_smoke"
SMOKE_TEXT = "Juno jobs smoke: AsyncIOScheduler fired on the shared serve loop."

_HANDLER_BY_ID = {
    DIGEST_DAILY_JOB_ID: digest_daily,
    DIGEST_WEEKLY_JOB_ID: digest_weekly,
    RESURFACING_JOB_ID: resurfacing,
    POLISH_JOB_ID: polish,
}


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


def register_job_specs(
    scheduler: AsyncIOScheduler,
    specs: tuple[JobSpec, ...] | list[JobSpec],
    *,
    app: Any | None = None,
) -> list[str]:
    """Add enabled cron jobs. Handlers may send Telegram; tests pass a mock bot."""
    added: list[str] = []
    for spec in specs:
        if not spec.enabled:
            logger.info("job %s disabled", spec.id)
            continue
        handler = _HANDLER_BY_ID.get(spec.id)
        if handler is None:
            logger.warning("job %s has no handler — skipped", spec.id)
            continue
        trigger = spec.trigger()

        async def run(*, fn=handler) -> None:
            await fn(app)

        scheduler.add_job(
            run,
            trigger=trigger,
            id=spec.id,
            replace_existing=True,
            misfire_grace_time=spec.misfire_grace_time,
        )
        added.append(spec.id)
        logger.info("job %s registered cron=%s tz=%s", spec.id, spec.crontab, spec.timezone)
    return added


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
    """Start AsyncIOScheduler on the serve loop and register builtin cron jobs."""
    settings: Settings = app.state.settings
    if not settings.juno_jobs_enabled:
        logger.info("jobs scheduler disabled (JUNO_JOBS_ENABLED=false)")
        app.state.scheduler = None
        app.state.job_specs = ()
        return None

    scheduler = create_scheduler(settings.juno_jobs_timezone)
    specs = apply_enabled_overrides(
        builtin_job_specs(settings),
        dict(getattr(app.state, "job_enabled_overrides", None) or {}),
    )
    app.state.job_specs = specs
    register_job_specs(scheduler, specs, app=app)
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


async def set_cron_job_enabled(app: Any, job_id: str, enabled: bool) -> str:
    """Persist enable flag and pause/resume (or register) the live job."""
    db = getattr(app.state, "db", None)
    if db is not None:
        from juno.jobs.registry import persist_job_enabled

        await persist_job_enabled(db, job_id, enabled)
    overrides = dict(getattr(app.state, "job_enabled_overrides", None) or {})
    overrides[job_id] = enabled
    app.state.job_enabled_overrides = overrides
    specs = tuple(getattr(app.state, "job_specs", None) or ())
    if specs:
        app.state.job_specs = apply_enabled_overrides(specs, {job_id: enabled})
    scheduler = getattr(app.state, "scheduler", None)
    if scheduler is None:
        return "Jobs scheduler is off."
    job = scheduler.get_job(job_id)
    if enabled:
        if job is not None:
            scheduler.resume_job(job_id)
        else:
            spec = next((s for s in (app.state.job_specs or ()) if s.id == job_id), None)
            if spec is None:
                return f"Unknown job {job_id}."
            register_job_specs(scheduler, (replace(spec, enabled=True),), app=app)
        return f"{job_id} is on."
    if job is not None:
        scheduler.pause_job(job_id)
    return f"{job_id} is off."


def format_jobs_status(app: Any) -> str:
    settings: Settings = app.state.settings
    scheduler = getattr(app.state, "scheduler", None)
    if not settings.juno_jobs_enabled or scheduler is None:
        return "Jobs scheduler is off (JUNO_JOBS_ENABLED=false)."
    specs = tuple(getattr(app.state, "job_specs", None) or ())
    lines = [f"Jobs timezone {settings.juno_jobs_timezone}:"]
    for spec in specs:
        job = scheduler.get_job(spec.id)
        if job is None or not spec.enabled:
            lines.append(f"• {spec.id}: off  ({spec.crontab})")
            continue
        nxt = job.next_run_time
        when = nxt.strftime("%Y-%m-%d %H:%M %Z") if nxt is not None else "paused"
        lines.append(f"• {spec.id}: on → {when}  ({spec.crontab})")
    lines.append("Toggle: /jobs daily|weekly|resurface|polish on|off")
    return "\n".join(lines)
