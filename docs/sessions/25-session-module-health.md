# Session 25 — Extension module health (#50)

**Date:** 2026-08-29  
**Issue:** [#50](https://github.com/Anna-Hax/JUNO/issues/50)  
**Branch:** `feat/extension-module-health-50`

## What changed

- Browser ingests update `module_health` row **`extension`** (success/error).
- `GET /status` includes `modules[]` (same data Telegram `/status` uses).

## Verify

```powershell
cd apps/core
$env:EMBEDDING_BACKEND='stub'
uv run pytest tests/test_ingest.py::test_browser_ingest_updates_extension_module_health tests/test_api.py::test_status_ok_with_good_token -q
```
