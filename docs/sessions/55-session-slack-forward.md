# Session 55 — Optional Slack forward (#112)

**Date:** 2026-09-05  
**Issue:** [#112](https://github.com/Anna-Hax/JUNO/issues/112)  
**Branch:** `feat/slack-forward-112`

## What changed

- Opt-in `JUNO_SLACK_FORWARD` ingests slack.com links as `source_type=slack` into the existing upload path.
- Not a workspace listener. Sensitive Slack batches still go through `/review`.
- Default off. Recorded in [ADR-11](../adr/011-slack-forward.md).

## Verify

```powershell
cd apps/core
$env:EMBEDDING_BACKEND='stub'
uv run pytest tests/test_bot.py -q
```
