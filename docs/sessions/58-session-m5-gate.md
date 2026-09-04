# Session 58 — M5 gate: v2.0 (#115)

**Date:** 2026-09-05  
**Issue:** [#115](https://github.com/Anna-Hax/JUNO/issues/115)  
**Branch:** `feat/m5-gate-115`

## What changed

- [`docs/v2.0-release-gate.md`](../v2.0-release-gate.md) — M5 checklist; all #106–#114 PRs listed.
- Package **2.0.0**. README + next-work mark M5 complete.
- ADRs 09–12 already cover drafts, trust, Slack, prune; ADR-07 polish jobs.

## Verify

```powershell
cd apps/core
$env:EMBEDDING_BACKEND='stub'
uv run pytest -q
uv run juno version   # expect 2.0.0
```

CI must stay green with `JUNO_JOBS_SMOKE` off and `JUNO_SLACK_FORWARD` off (no live Telegram/Slack).
