# Session 43 — Temporal queries (#90)

**Date:** 2026-09-04  
**Issue:** [#90](https://github.com/Anna-Hax/JUNO/issues/90)  
**Branch:** `feat/rag-temporal-90`

## What changed

- Detect evolution/timeline phrasing; `/search` and Telegram retrieve return `mode=temporal` with hits ordered by `captured_at` and dated citations.

## Verify

```powershell
cd apps/core
$env:EMBEDDING_BACKEND='stub'
uv run pytest tests/test_rag.py -q
```
