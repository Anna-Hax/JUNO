# Session 36 — Digest enrichment for IDE (#71)

**Date:** 2026-09-02  
**Issue:** [#71](https://github.com/Anna-Hax/JUNO/issues/71)  
**Branch:** `feat/ide-digest-71`

## What changed

- `/digest today|week` groups **IDE chats** and **IDE errors** beside browser reading and uploads.

## Verify

```powershell
cd apps/core
$env:EMBEDDING_BACKEND='stub'
uv run pytest tests/test_bot.py::test_format_digest_groups_ide_chats_and_errors -q
```
