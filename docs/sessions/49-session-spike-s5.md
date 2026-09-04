# Session 49 — Spike S5 (#106)

**Date:** 2026-09-05  
**Issue:** [#106](https://github.com/Anna-Hax/JUNO/issues/106) — Spike S5: one auto-generated draft through HITL  
**Epic:** [#28](https://github.com/Anna-Hax/JUNO/issues/28)  
**Branch:** `feat/spike-s5-106`

## Decision

**Template journal snippet** queued as `review_items.kind=draft`. Approve confirms; **never auto-publishes** (no capture, no file, no canonical Telegram). LLM generation deferred. Recorded in [ADR-09](../adr/009-draft-artifacts-hitl.md).

## What changed

- `juno.drafts.generate` — deterministic paragraph from recent capture titles (placeholder if empty).
- `ReviewQueue.propose_draft` + `/review` card copy for drafts.
- Serve lifespan enqueues one draft when `JUNO_DRAFTS_SMOKE=true` (skipped under `/pause`).
- Knobs: `JUNO_DRAFTS_SMOKE` (default off), `JUNO_DRAFTS_GENERATOR=template`.
- Pytest covers enqueue / Approve / Reject / Skip without a live LLM or Telegram.

## Smoke

With repo-root `.env` and `JUNO_DRAFTS_SMOKE=true`:

```powershell
cd apps/core
uv run juno serve
```

Telegram `/review` should show a pending **Draft journal** card. Approve keeps it confirmed with `published=false`. Turn `JUNO_DRAFTS_SMOKE` back off afterwards so serve restarts do not re-queue.

## Deferred to #107+

Draft kinds scaffold, flashcards/SRS, LLM journal/README, skill-gap, trust dial, Slack forward, prune-with-confirm, polish module health, M5 gate.

## Links

| Doc | Role |
|-----|------|
| [009-draft-artifacts-hitl.md](../adr/009-draft-artifacts-hitl.md) | ADR |
| [next-work.md](../next-work.md) | M5 queue |
