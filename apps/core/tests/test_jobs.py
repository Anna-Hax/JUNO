from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from juno.config import Settings
from juno.jobs import (
    DIGEST_DAILY_JOB_ID,
    DIGEST_WEEKLY_JOB_ID,
    RESURFACING_JOB_ID,
    SMOKE_JOB_ID,
    builtin_job_specs,
    create_scheduler,
    enabled_job_ids,
    register_job_specs,
    register_smoke_job,
    send_allowlisted_push,
    start_jobs,
    stop_jobs,
)
from juno.jobs.registry import JobSpec


def test_create_scheduler_is_asyncio_scheduler():
    scheduler = create_scheduler("UTC")
    assert isinstance(scheduler, AsyncIOScheduler)
    assert scheduler.timezone.key == "UTC"


@pytest.mark.asyncio
async def test_date_job_fires_on_the_running_event_loop():
    loop = asyncio.get_running_loop()
    fired = asyncio.Event()
    seen: list[int] = []

    async def job() -> None:
        seen.append(id(asyncio.get_running_loop()))
        fired.set()

    scheduler = create_scheduler("UTC")
    scheduler.start()
    try:
        register_smoke_job(scheduler, coro_factory=job, delay_seconds=0.05)
        await asyncio.wait_for(fired.wait(), timeout=2)
    finally:
        scheduler.shutdown(wait=False)

    assert seen == [id(loop)]


@pytest.mark.asyncio
async def test_send_allowlisted_push_reaches_each_user(settings: Settings):
    settings.allowed_telegram_user_ids = "11, 22"
    bot = AsyncMock()
    sent = await send_allowlisted_push(bot, settings, "hello")
    assert sent == 2
    chats = sorted(call.kwargs["chat_id"] for call in bot.send_message.await_args_list)
    assert chats == [11, 22]
    assert all(call.kwargs["text"] == "hello" for call in bot.send_message.await_args_list)


@pytest.mark.asyncio
async def test_send_allowlisted_push_skips_when_paused_or_empty(settings: Settings):
    bot = AsyncMock()
    settings.allowed_telegram_user_ids = "11"
    skipped = await send_allowlisted_push(bot, settings, "x", is_paused=lambda: True)
    assert skipped == 0
    bot.send_message.assert_not_awaited()

    settings.allowed_telegram_user_ids = ""
    empty = await send_allowlisted_push(bot, settings, "x")
    assert empty == 0
    bot.send_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_start_jobs_disabled_does_not_start_scheduler(settings: Settings):
    settings.juno_jobs_enabled = False
    app = SimpleNamespace(state=SimpleNamespace(settings=settings, ptb=None, capture_paused=False))
    assert start_jobs(app) is None
    assert app.state.scheduler is None
    assert app.state.job_specs == ()
    stop_jobs(app)


@pytest.mark.asyncio
async def test_start_jobs_smoke_registers_one_shot(settings: Settings):
    settings.juno_jobs_enabled = True
    settings.juno_jobs_smoke = True
    settings.allowed_telegram_user_ids = "42"
    bot = AsyncMock()
    app = SimpleNamespace(
        state=SimpleNamespace(
            settings=settings,
            ptb=SimpleNamespace(bot=bot),
            capture_paused=False,
        )
    )
    scheduler = start_jobs(app)
    try:
        assert isinstance(scheduler, AsyncIOScheduler)
        assert scheduler.running
        job = scheduler.get_job(SMOKE_JOB_ID)
        assert job is not None
        assert job.next_run_time is not None
        assert job.next_run_time <= datetime.now(UTC) + timedelta(seconds=5)
    finally:
        stop_jobs(app)
    assert app.state.scheduler is None


def test_builtin_registry_defaults_without_telegram(settings: Settings):
    specs = builtin_job_specs(settings)
    ids = [spec.id for spec in specs]
    assert ids == [DIGEST_DAILY_JOB_ID, DIGEST_WEEKLY_JOB_ID, RESURFACING_JOB_ID]
    assert enabled_job_ids(specs) == [DIGEST_DAILY_JOB_ID, DIGEST_WEEKLY_JOB_ID]
    daily = next(spec for spec in specs if spec.id == DIGEST_DAILY_JOB_ID)
    assert daily.crontab == "0 7 * * *"
    assert daily.trigger() is not None


def test_disabled_job_is_not_added_to_scheduler(settings: Settings):
    settings.juno_jobs_digest_daily = False
    settings.juno_jobs_digest_weekly = False
    settings.juno_jobs_resurfacing = False
    scheduler = create_scheduler("UTC")
    added = register_job_specs(scheduler, builtin_job_specs(settings), app=None)
    assert added == []
    assert scheduler.get_job(DIGEST_DAILY_JOB_ID) is None


def test_register_job_specs_without_starting_or_telegram(settings: Settings):
    settings.juno_jobs_resurfacing = True
    scheduler = create_scheduler("UTC")
    added = register_job_specs(scheduler, builtin_job_specs(settings), app=None)
    assert DIGEST_DAILY_JOB_ID in added
    assert DIGEST_WEEKLY_JOB_ID in added
    assert RESURFACING_JOB_ID in added
    assert scheduler.get_job(DIGEST_DAILY_JOB_ID) is not None
    assert scheduler.running is False


def test_invalid_crontab_raises(settings: Settings):
    spec = JobSpec(id="bad", crontab="not-a-cron", enabled=True, timezone="UTC")
    with pytest.raises(ValueError):
        spec.trigger()


@pytest.mark.asyncio
async def test_start_jobs_registers_enabled_cron_jobs(settings: Settings):
    settings.juno_jobs_enabled = True
    settings.juno_jobs_smoke = False
    settings.juno_jobs_digest_weekly = False
    app = SimpleNamespace(state=SimpleNamespace(settings=settings, ptb=None, capture_paused=False))
    scheduler = start_jobs(app)
    try:
        assert scheduler.get_job(DIGEST_DAILY_JOB_ID) is not None
        assert scheduler.get_job(DIGEST_WEEKLY_JOB_ID) is None
        assert scheduler.get_job(RESURFACING_JOB_ID) is None
    finally:
        stop_jobs(app)


@pytest.mark.asyncio
async def test_push_scheduled_digest_sends_grouped_text(settings: Settings):
    from juno.graph.db import Database
    from juno.ingest.pipeline import IngestPipeline
    from juno.jobs.handlers import push_scheduled_digest

    settings.allowed_telegram_user_ids = "42"
    db = Database(settings)
    await db.migrate()
    bot = AsyncMock()
    app = SimpleNamespace(
        state=SimpleNamespace(
            settings=settings,
            db=db,
            ptb=SimpleNamespace(bot=bot),
            capture_paused=False,
        )
    )
    try:
        await IngestPipeline(db).ingest_text("Ownership notes", source_type="upload", title="rust")
        sent = await push_scheduled_digest(app, "today")
        assert sent == 1
        text = bot.send_message.await_args.kwargs["text"]
        assert "Morning digest" in text
        assert "rust" in text
        bot.send_message.reset_mock()
        app.state.capture_paused = True
        skipped = await push_scheduled_digest(app, "today")
        assert skipped == 0
        bot.send_message.assert_not_awaited()
    finally:
        await db.dispose()


def test_apply_enabled_overrides(settings: Settings):
    from juno.jobs import apply_enabled_overrides

    specs = builtin_job_specs(settings)
    patched = apply_enabled_overrides(specs, {DIGEST_DAILY_JOB_ID: False})
    assert enabled_job_ids(patched) == [DIGEST_WEEKLY_JOB_ID]
