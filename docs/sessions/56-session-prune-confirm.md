# Session 56 — Prune-with-confirm (#113)

**Date:** 2026-09-05  
**Issue:** [#113](https://github.com/Anna-Hax/JUNO/issues/113)  
**Branch:** `feat/prune-confirm-113`

## What changed

- `/prune` lists old unused / aged failed captures. `/prune confirm` queues HITL `kind=prune`.
- Approve archives rows and drops their Chroma ids. Reject leaves them. Never a silent delete; not `juno wipe`.
- CLI `juno prune` is dry-run unless `--confirm prune-selected`. Optional `--export` before queueing.
- Trust category `prune` is locked. Recorded in [ADR-12](../adr/012-prune-with-confirm.md).

## Verify

```powershell
cd apps/core
$env:EMBEDDING_BACKEND='stub'
uv run pytest tests/test_prune.py tests/test_trust.py tests/test_bot.py -q
```
