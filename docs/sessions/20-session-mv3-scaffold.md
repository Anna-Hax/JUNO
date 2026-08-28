# Session 20 — MV3 scaffold (#45)

**Date:** 2026-08-29  
**Issue:** [#45](https://github.com/Anna-Hax/JUNO/issues/45)  
**Branch:** `feat/mv3-scaffold-45`

## What changed

- Refactored extension into `lib/config.js` + `lib/api.js`; thin `background.js` service worker.
- Separate **popup** (connection status) vs **options** (token + base URL).
- `apps/extension/README.md` with load-unpacked steps.
- CI extension job validates lib/, popup, and README.

## Verify

```powershell
# CI locally
python -m json.tool apps/extension/manifest.json
# Load unpacked per apps/extension/README.md; popup shows Connected when serve is up.
```
