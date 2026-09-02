# Session 33 — HITL for IDE error-match and chat batches (#68)

**Date:** 2026-09-02  
**Issue:** [#68](https://github.com/Anna-Hax/JUNO/issues/68)  
**Branch:** `feat/ide-hitl-68`

## What changed

- Review kinds `error_match` and `ide_batch` (same Approve / Reject / Skip as merges).
- Error-match stays unconfirmed until Approve (same root cause vs similar stack).
- Bulk/sensitive IDE chat batches stay reviewable.

## Verify

```powershell
cd apps/core
$env:EMBEDDING_BACKEND='stub'
uv run pytest tests/test_review.py tests/test_bot_review.py -q
```
