# Session 40 — Scheduler scaffold (#87)

**Date:** 2026-09-04  
**Issue:** [#87](https://github.com/Anna-Hax/JUNO/issues/87)  
**Branch:** `feat/jobs-scaffold-87`

## What changed

- `juno.jobs.registry` — named specs `digest_daily`, `digest_weekly`, `resurfacing` with enable + crontab from settings.
- Serve lifespan registers enabled cron jobs (tick handlers only; no Telegram until #88/#89).
- CI imports/registers jobs without a bot.

## Verify

```powershell
cd apps/core
$env:EMBEDDING_BACKEND='stub'
uv run pytest tests/test_jobs.py -q
```

## Deferred

Digest push text (#88), resurfacing body (#89), module health (#94).

## Links

| Doc | Role |
|-----|------|
| [007-proactive-jobs-shared-loop.md](../adr/007-proactive-jobs-shared-loop.md) | ADR |
| [next-work.md](../next-work.md) | M4 queue |
