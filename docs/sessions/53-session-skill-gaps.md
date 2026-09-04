# Session 53 — Skill-gap tracking (#110)

**Date:** 2026-09-05  
**Issue:** [#110](https://github.com/Anna-Hax/JUNO/issues/110)  
**Branch:** `feat/skill-gaps-110`

## What changed

- `/gaps` finds repeat IDE errors and unfinished browser reads (no highlights, stale URI).
- High-confidence repeats are listed; low-confidence flags go to `/review` (`skill_gap`).
- Seen keys persist so Juno does not nag. `/pause` skips the scan.

## Verify

```powershell
cd apps/core
$env:EMBEDDING_BACKEND='stub'
uv run pytest tests/test_gaps.py -q
```
