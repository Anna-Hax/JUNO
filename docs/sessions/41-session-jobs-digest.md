# Session 41 — Scheduled push digests (#88)

**Date:** 2026-09-04  
**Issue:** [#88](https://github.com/Anna-Hax/JUNO/issues/88)  
**Branch:** `feat/jobs-digest-88`

## What changed

- Daily (07:00) and weekly (Monday 07:00, timezone knob) jobs push `/digest`-style grouped summaries to the allowlist.
- Global `/pause` skips pushes. `/jobs` lists next runs; `/jobs daily|weekly on|off` persists and pause/resumes the live job.

## Verify

```powershell
cd apps/core
$env:EMBEDDING_BACKEND='stub'
uv run pytest tests/test_jobs.py tests/test_bot.py -q
```

## Deferred

Resurfacing body (#89), module health (#94).

## Links

| Doc | Role |
|-----|------|
| [007-proactive-jobs-shared-loop.md](../adr/007-proactive-jobs-shared-loop.md) | ADR |
