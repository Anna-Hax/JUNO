# Session 39 — Spike S4 (#86)

**Date:** 2026-09-04  
**Issue:** [#86](https://github.com/Anna-Hax/JUNO/issues/86) — Spike S4: APScheduler on shared loop + one Telegram push smoke  
**Epic:** [#27](https://github.com/Anna-Hax/JUNO/issues/27)  
**Branch:** `feat/spike-s4-86`

## Decision

**AsyncIOScheduler 3.11** on the uvicorn/PTB loop (not `BackgroundScheduler`, not a second process, not APScheduler 4). Recorded in [ADR-07](../adr/007-proactive-jobs-shared-loop.md).

## What changed

- `juno.jobs.scheduler` — create/start/stop scheduler; one-shot smoke job; allowlisted `send_message`.
- Serve lifespan starts jobs after PTB, stops them before PTB.
- Knobs: `JUNO_JOBS_ENABLED`, `JUNO_JOBS_TIMEZONE`, `JUNO_JOBS_SMOKE`.
- Pytest covers same-loop fire + mock Telegram (no live bot in CI).

## Smoke

With repo-root `.env` (token + allowlist) and `JUNO_JOBS_SMOKE=true`:

```powershell
cd apps/core
uv run juno serve
```

Within a few seconds the allowlisted Telegram chat should receive:
`Juno jobs smoke: AsyncIOScheduler fired on the shared serve loop.`

Turn `JUNO_JOBS_SMOKE` back off afterwards so serve restarts do not re-push.

## Deferred to #87+

Job registry + cron settings, scheduled digests, resurfacing, temporal queries, voice/mobile, PC-off runbook, `jobs` module health, M4 gate.

## Links

| Doc | Role |
|-----|------|
| [007-proactive-jobs-shared-loop.md](../adr/007-proactive-jobs-shared-loop.md) | ADR |
| [next-work.md](../next-work.md) | M4 queue |
