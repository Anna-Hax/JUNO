# Session 32 — Terminal error capture (#67)

**Date:** 2026-09-02  
**Issue:** [#67](https://github.com/Anna-Hax/JUNO/issues/67)  
**Branch:** `feat/ide-errors-67`

## What changed

- `extract_errors()` reads `toolFormerData` on composer bubbles (`run_terminal_command_v2` + `status=error` or error-like output).
- Ingest as `source_type=ide` with `raw_json.kind=cursor_error` (`cursor://error/{composer}/{bubble}`).
- `sync.py` posts errors next to chat sessions.

## Verify

```powershell
cd apps/core
$env:EMBEDDING_BACKEND='stub'
uv run pytest tests/test_ide_vscdb.py -q
python ..\..\apps\ide\sync.py --once --dry-run
```
