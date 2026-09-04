"""Named job specs from settings, plus optional AppSetting enable overrides."""

from __future__ import annotations

from dataclasses import dataclass, replace
from zoneinfo import ZoneInfo

from apscheduler.triggers.cron import CronTrigger
from sqlalchemy.ext.asyncio import AsyncSession

from juno.config import Settings
from juno.graph.db import Database
from juno.models import AppSetting

DIGEST_DAILY_JOB_ID = "digest_daily"
DIGEST_WEEKLY_JOB_ID = "digest_weekly"
RESURFACING_JOB_ID = "resurfacing"
TOGGLEABLE_JOBS = {
    "daily": DIGEST_DAILY_JOB_ID,
    "weekly": DIGEST_WEEKLY_JOB_ID,
    "resurface": RESURFACING_JOB_ID,
}


@dataclass(frozen=True)
class JobSpec:
    id: str
    crontab: str
    enabled: bool
    timezone: str = "UTC"
    misfire_grace_time: int = 3600

    def trigger(self) -> CronTrigger:
        return CronTrigger.from_crontab(self.crontab, timezone=ZoneInfo(self.timezone))


def builtin_job_specs(settings: Settings) -> tuple[JobSpec, ...]:
    tz = settings.juno_jobs_timezone
    return (
        JobSpec(
            id=DIGEST_DAILY_JOB_ID,
            crontab=settings.juno_jobs_digest_daily_cron,
            enabled=settings.juno_jobs_digest_daily,
            timezone=tz,
        ),
        JobSpec(
            id=DIGEST_WEEKLY_JOB_ID,
            crontab=settings.juno_jobs_digest_weekly_cron,
            enabled=settings.juno_jobs_digest_weekly,
            timezone=tz,
        ),
        JobSpec(
            id=RESURFACING_JOB_ID,
            crontab=settings.juno_jobs_resurfacing_cron,
            enabled=settings.juno_jobs_resurfacing,
            timezone=tz,
        ),
    )


def enabled_job_ids(
    specs: tuple[JobSpec, ...] | None = None,
    settings: Settings | None = None,
) -> list[str]:
    if specs is None:
        if settings is None:
            raise ValueError("specs or settings required")
        specs = builtin_job_specs(settings)
    return [spec.id for spec in specs if spec.enabled]


def job_enabled_setting_key(job_id: str) -> str:
    return f"jobs.enabled.{job_id}"


def apply_enabled_overrides(
    specs: tuple[JobSpec, ...],
    overrides: dict[str, bool],
) -> tuple[JobSpec, ...]:
    if not overrides:
        return specs
    return tuple(
        replace(spec, enabled=overrides[spec.id]) if spec.id in overrides else spec
        for spec in specs
    )


async def load_job_enabled_overrides(db: Database) -> dict[str, bool]:
    keys = (DIGEST_DAILY_JOB_ID, DIGEST_WEEKLY_JOB_ID, RESURFACING_JOB_ID)

    async def fn(session: AsyncSession) -> dict[str, bool]:
        out: dict[str, bool] = {}
        for job_id in keys:
            row = await session.get(AppSetting, job_enabled_setting_key(job_id))
            if row is None:
                continue
            out[job_id] = row.value.strip().lower() in {"1", "true", "yes", "on"}
        return out

    return await db.read(fn)


async def persist_job_enabled(db: Database, job_id: str, enabled: bool) -> None:
    key = job_enabled_setting_key(job_id)
    value = "true" if enabled else "false"

    async def fn(session: AsyncSession) -> None:
        row = await session.get(AppSetting, key)
        if row is None:
            session.add(AppSetting(key=key, value=value))
        else:
            row.value = value

    await db.write(fn)
