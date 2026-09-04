# Session 42 — Contextual resurfacing (#89)

**Date:** 2026-09-04  
**Issue:** [#89](https://github.com/Anna-Hax/JUNO/issues/89)  
**Branch:** `feat/jobs-resurface-89`

## What changed

- Hourly `resurfacing` job: recent captures vs older vector neighbors.
- High confidence (≥ 0.55) → allowlisted Telegram “this came up again” with citations.
- Low confidence → HITL `resurface` review card. Duplicate pairs are remembered.

## Verify

```powershell
cd apps/core
$env:EMBEDDING_BACKEND='stub'
uv run pytest tests/test_jobs.py -q
```

## Links

| Doc | Role |
|-----|------|
| [007-proactive-jobs-shared-loop.md](../adr/007-proactive-jobs-shared-loop.md) | ADR |
