# Session 27 — Digest enrichment (#52)

**Date:** 2026-08-29  
**Issue:** [#52](https://github.com/Anna-Hax/JUNO/issues/52)  
**Branch:** `feat/digest-enrichment-52`

## What changed

- `/digest today|week` groups **Browser reading** vs **Uploads / other** sections.

## Verify

```powershell
cd apps/core
uv run pytest tests/test_bot.py::test_format_digest_groups_browser_reading -q
```
