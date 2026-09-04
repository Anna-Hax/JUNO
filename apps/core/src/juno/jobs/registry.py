"""Named job specs from settings. Pure — no Telegram, no running scheduler."""

from __future__ import annotations

from dataclasses import dataclass
from zoneinfo import ZoneInfo

from apscheduler.triggers.cron import CronTrigger

from juno.config import Settings

DIGEST_DAILY_JOB_ID = "digest_daily"
DIGEST_WEEKLY_JOB_ID = "digest_weekly"
RESURFACING_JOB_ID = "resurfacing"


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
