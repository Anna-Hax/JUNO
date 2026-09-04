# Session 54 — Trust dial (#111)

**Date:** 2026-09-05  
**Issue:** [#111](https://github.com/Anna-Hax/JUNO/issues/111)  
**Branch:** `feat/trust-dial-111`

## What changed

- Per-category dials in `settings`; `/trust` and `/status` show them.
- Five approved merges turn merge auto-commit on for high-confidence proposes.
- `mobile` and `drafts` stay gated. [ADR-10](../adr/010-trust-dials.md).

## Verify

```powershell
cd apps/core
$env:EMBEDDING_BACKEND='stub'
uv run pytest tests/test_trust.py -q
```
