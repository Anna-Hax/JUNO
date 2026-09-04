from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from juno.config import Settings
from juno.jobs import (
    SMOKE_JOB_ID,
    create_scheduler,
    register_smoke_job,
    send_allowlisted_push,
    start_jobs,
    stop_jobs,
)


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
