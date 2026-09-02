# Session 35 — Cross-reference IDE vs browser + inbox (#70)

**Date:** 2026-09-02  
**Issue:** [#70](https://github.com/Anna-Hax/JUNO/issues/70)  
**Branch:** `feat/ide-crossref-70`

## What changed

- `related_captures()` matches IDE hits to browser/upload rows (GitHub-issue style).
- Query replies append **You also read or uploaded notes on:** when IDE hits have related context.

## Verify

```powershell
cd apps/core
$env:EMBEDDING_BACKEND='stub'
uv run pytest tests/test_bot.py -q
```
