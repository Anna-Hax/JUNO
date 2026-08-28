# Session 21 — Browser URL + title + timestamp (#46)

**Date:** 2026-08-29  
**Issue:** [#46](https://github.com/Anna-Hax/JUNO/issues/46)  
**Branch:** `feat/browser-capture-timestamp-46`

## What changed

- Extension `lib/capture.js` sends `visited_at` + `raw_json` on browser ingests.
- `ingest_payload` persists client timestamp as `captures.captured_at` and stores browser metadata in `raw_json`.
- Test: `test_browser_payload_stores_visited_at_and_raw_json`.

## Verify

```powershell
cd apps/core
$env:EMBEDDING_BACKEND='stub'
uv run pytest tests/test_ingest.py::test_browser_payload_stores_visited_at_and_raw_json -q
```
