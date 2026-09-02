# Session 38 — M3 gate: IDE tests + v1.2 (#73)

**Date:** 2026-09-02  
**Issue:** [#73](https://github.com/Anna-Hax/JUNO/issues/73)  
**Branch:** `feat/m3-gate-73`

## What changed

- Operator runbook in [`apps/ide/README.md`](../../apps/ide/README.md).
- [ADR-06](../adr/006-ide-adapter-client.md) records landed M3 client behaviour (#65–#72).
- [`docs/v1.2-release-gate.md`](../v1.2-release-gate.md) — M3 checklist; package **1.2.0**.

## Verify

```powershell
python scripts/validate-ide.py
cd apps/core
$env:EMBEDDING_BACKEND='stub'
uv run pytest tests/test_ide_scaffold.py tests/test_ide_vscdb.py -q
uv run juno version   # expect 1.2.0
```

Poll Cursor chats per the adapter runbook.
