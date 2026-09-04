# Session 48 — M4 gate: jobs tests + v1.3 (#95)

**Date:** 2026-09-04  
**Issue:** [#95](https://github.com/Anna-Hax/JUNO/issues/95)  
**Branch:** `feat/m4-gate-95`

## What changed

- [ADR-07](../adr/007-proactive-jobs-shared-loop.md) records landed M4 job behaviour (#86–#94).
- [`docs/v1.3-release-gate.md`](../v1.3-release-gate.md) — M4 checklist; package **1.3.0**.
- README + ADR-01 follow-ups point at completed proactive jobs, not a future spike.

## Verify

```powershell
cd apps/core
$env:EMBEDDING_BACKEND='stub'
uv run pytest tests/test_jobs.py tests/test_transcribe.py tests/test_rag.py -q
uv run juno version   # expect 1.3.0
```

CI must stay green with `JUNO_JOBS_SMOKE` off (no live Telegram).
