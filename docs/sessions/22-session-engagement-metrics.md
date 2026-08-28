# Session 22 — Engagement metrics (#47)

**Date:** 2026-08-29  
**Issue:** [#47](https://github.com/Anna-Hax/JUNO/issues/47)  
**Branch:** `feat/engagement-metrics-47`

## What changed

- `content.js` tracks **active time** and **scroll depth**; reports on interval and page hide.
- Background defers ingest until tab switch/close/page-done so metrics are included.
- Metrics stored in `captures.raw_json.metrics` (`active_time_ms`, `scroll_depth`).

## Verify

```powershell
cd apps/core
$env:EMBEDDING_BACKEND='stub'
uv run pytest tests/test_ingest.py::test_browser_payload_stores_engagement_metrics -q
```

Load extension, visit a page, scroll, switch tabs — ingest logs should include metrics.
