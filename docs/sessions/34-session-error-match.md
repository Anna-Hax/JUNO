# Session 34 — Error-matching retrieval (#69)

**Date:** 2026-09-02  
**Issue:** [#69](https://github.com/Anna-Hax/JUNO/issues/69)  
**Branch:** `feat/ide-error-match-69`

## What changed

- `match_past_errors()` prefers `source_type=ide` hits, keeps retrieve-only when the LLM is down, and queues `error_match` HITL before reuse.
- Telegram queries that look like errors use this path.

## Verify

```powershell
cd apps/core
$env:EMBEDDING_BACKEND='stub'
uv run pytest tests/test_rag.py -q
```
