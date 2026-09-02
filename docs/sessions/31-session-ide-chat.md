# Session 31 — Chat/composer ingest (#66)

**Date:** 2026-09-02  
**Issue:** [#66](https://github.com/Anna-Hax/JUNO/issues/66)  
**Branch:** `feat/ide-chat-66`

## What changed

- `source_type=ide` stores `raw_json.kind=cursor_chat` plus bubble list.
- Re-sync is keyed by `uri` (`cursor://composer/{id}`): unchanged payloads keep one row; newer `updated_at` / text replaces chunks in place.

## Verify

```powershell
cd apps/core
$env:EMBEDDING_BACKEND='stub'
uv run pytest tests/test_ide_vscdb.py -q
```
