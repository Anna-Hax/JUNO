# Session 26 — Cross-reference browser vs inbox (#51)

**Date:** 2026-08-29  
**Issue:** [#51](https://github.com/Anna-Hax/JUNO/issues/51)  
**Branch:** `feat/cross-reference-51`

## What changed

- `related_upload_captures()` finds upload/inbox rows matching browser hit titles/domains.
- Query replies append **You also uploaded notes on:** when browser hits have related uploads.

## Verify

```powershell
cd apps/core
$env:EMBEDDING_BACKEND='stub'
uv run pytest tests/test_bot.py::test_related_upload_captures_finds_upload_for_browser_hit -q
```
