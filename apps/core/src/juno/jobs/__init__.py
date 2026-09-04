"""Scheduled jobs on the shared asyncio loop (M4 / ADR-07)."""

from juno.jobs.registry import (
    DIGEST_DAILY_JOB_ID,
    DIGEST_WEEKLY_JOB_ID,
    RESURFACING_JOB_ID,
    TOGGLEABLE_JOBS,
    JobSpec,
    apply_enabled_overrides,
    builtin_job_specs,
    enabled_job_ids,
    load_job_enabled_overrides,
    persist_job_enabled,
)
from juno.jobs.scheduler import (
    SMOKE_JOB_ID,
    SMOKE_TEXT,
    create_scheduler,
    format_jobs_status,
    register_job_specs,
    register_smoke_job,
    send_allowlisted_push,
    set_cron_job_enabled,
    start_jobs,
    stop_jobs,
)

__all__ = [
    "DIGEST_DAILY_JOB_ID",
    "DIGEST_WEEKLY_JOB_ID",
    "RESURFACING_JOB_ID",
    "SMOKE_JOB_ID",
    "SMOKE_TEXT",
    "TOGGLEABLE_JOBS",
    "JobSpec",
    "apply_enabled_overrides",
    "builtin_job_specs",
    "create_scheduler",
    "enabled_job_ids",
    "format_jobs_status",
    "load_job_enabled_overrides",
    "persist_job_enabled",
    "register_job_specs",
    "register_smoke_job",
    "send_allowlisted_push",
    "set_cron_job_enabled",
    "start_jobs",
    "stop_jobs",
]
