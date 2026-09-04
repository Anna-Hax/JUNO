# Session 45 — Mobile depth HITL (#92)

**Date:** 2026-09-04  
**Issue:** [#92](https://github.com/Anna-Hax/JUNO/issues/92)  
**Branch:** `feat/hitl-mobile-92`

## What changed

- Telegram forwards, docs, and voice notes enqueue HITL `mobile_batch` after ingest.
- URL-only captures still auto-commit (high-confidence). Offline OS monitoring stays out of scope.

## Verify

```powershell
cd apps/core
$env:EMBEDDING_BACKEND='stub'
uv run pytest tests/test_bot.py tests/test_review.py -q
```
