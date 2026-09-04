# Session 47 — Jobs module health (#94)

**Date:** 2026-09-04  
**Issue:** [#94](https://github.com/Anna-Hax/JUNO/issues/94)  
**Branch:** `feat/jobs-health-94`

## What changed

- `module_health.jobs` updates on digest/resurfacing ticks (including `/pause` skips) and scheduler start.
- Telegram `/status` and `GET /status.modules` list the `jobs` row.
- Global `/pause` still skips outbound pushes; the skip is recorded as a successful health tick.

## Verify

```powershell
cd apps/core
$env:EMBEDDING_BACKEND='stub'
uv run pytest tests/test_jobs.py tests/test_bot.py::test_status_reports_pause_and_health -q
```
