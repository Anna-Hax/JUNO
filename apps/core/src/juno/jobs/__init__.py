"""Scheduled jobs on the shared asyncio loop (M4 / ADR-07)."""

from juno.jobs.registry import (
    DIGEST_DAILY_JOB_ID,
    DIGEST_WEEKLY_JOB_ID,
    RESURFACING_JOB_ID,
    JobSpec,
    builtin_job_specs,
    enabled_job_ids,
)
from juno.jobs.scheduler import (
    SMOKE_JOB_ID,
    SMOKE_TEXT,
    create_scheduler,
    register_job_specs,
    register_smoke_job,
    send_allowlisted_push,
    start_jobs,
    stop_jobs,
)

__all__ = [
    "DIGEST_DAILY_JOB_ID",
    "DIGEST_WEEKLY_JOB_ID",
    "RESURFACING_JOB_ID",
    "SMOKE_JOB_ID",
    "SMOKE_TEXT",
    "JobSpec",
    "builtin_job_specs",
    "create_scheduler",
    "enabled_job_ids",
    "register_job_specs",
    "register_smoke_job",
    "send_allowlisted_push",
    "start_jobs",
    "stop_jobs",
]
