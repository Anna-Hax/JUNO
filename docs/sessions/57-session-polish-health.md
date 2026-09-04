# Session 57 — Polish jobs module health (#114)

**Date:** 2026-09-05  
**Issue:** [#114](https://github.com/Anna-Hax/JUNO/issues/114)  
**Branch:** `feat/polish-health-114`

## What changed

- Named cron `polish` (default `0 8 * * *`) queues HITL flashcard drafts and a journal draft if none is pending.
- `module_health.polish` last success/error shows on `/status` and `GET /status.modules`.
- `/pause` skips generation and does not push draft text. ADR-07 updated.

## Verify

```powershell
cd apps/core
$env:EMBEDDING_BACKEND='stub'
uv run pytest tests/test_jobs.py tests/test_bot.py -q
```
