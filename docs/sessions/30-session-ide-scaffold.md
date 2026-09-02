# Session 30 — IDE adapter scaffold (#65)

**Date:** 2026-09-02  
**Issue:** [#65](https://github.com/Anna-Hax/JUNO/issues/65)  
**Branch:** `feat/ide-scaffold-65`

## What changed

- Split `apps/ide/` into `config.py` + `api.py` + `cursor_vscdb.py`; `smoke.py` stays one-shot export.
- `sync.py` polls Cursor paths (`--once` / `--watch`), watermark in `data/ide-adapter.json`, backs off on 423.
- `.env.example` Cursor path + poll settings; `scripts/validate-ide.py` + CI IDE workflow.

## Verify

```powershell
python scripts/validate-ide.py
python apps/ide/sync.py --once --dry-run
cd apps/core
$env:EMBEDDING_BACKEND='stub'
uv run pytest tests/test_ide_scaffold.py tests/test_ide_vscdb.py -q
```
