# Session 46 — PC-off / serve-down status (#93)

**Date:** 2026-09-04  
**Issue:** [#93](https://github.com/Anna-Hax/JUNO/issues/93)  
**Branch:** `feat/serve-down-93`

## What changed

- `module_health.core` heartbeat when `juno serve` starts.
- `/status` and README explain that a stopped PC/process cannot answer Telegram (~24h queue).

## Verify

```powershell
cd apps/core
$env:EMBEDDING_BACKEND='stub'
uv run pytest tests/test_bot.py -q
```
