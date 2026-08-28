# Session 28 — M2 gate: extension tests + v1.1 (#53)

**Date:** 2026-08-29  
**Issue:** [#53](https://github.com/Anna-Hax/JUNO/issues/53)  
**Branch:** `feat/m2-gate-53`

## What changed

- `scripts/validate-extension.py` — manifest, file graph, optional Node JS syntax check.
- Core pytest invokes the validator; CI Extension workflow runs it.
- [`docs/v1.1-release-gate.md`](../v1.1-release-gate.md) — M2 checklist; package **1.1.0**.

## Verify

```powershell
python scripts/validate-extension.py
cd apps/core
$env:EMBEDDING_BACKEND='stub'
uv run pytest tests/test_extension_validate.py -q
uv run juno version   # expect 1.1.0
```

Load unpacked extension per [`apps/extension/README.md`](../../apps/extension/README.md).
