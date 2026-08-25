# Session log: HITL review queue (#20)

**Date:** 2026-08-26  
**Repo:** [https://github.com/Anna-Hax/JUNO](https://github.com/Anna-Hax/JUNO)  
**Plan:** Personal Knowledge Graph (local-first Python + Telegram)  
**Scope of this session:** M1 issue **#20** — `review_items` queue + Telegram `/review` inline Approve / Reject / Skip.

---

## Summary

Proposed graph merges now land as a `pending` edge plus a `review_items` row. They do not become `committed` until an allowlisted user taps **Approve**. `/review` shows the oldest open item with inline buttons; Reject leaves the edge unapplied; Skip keeps it in the queue.

Work is on branch `feat/hitl-review` (from `main` after ingest #16). PR / `Closes #20` not opened yet.

---

## What changed

### Code

| Path | Role |
|------|------|
| `apps/core/src/juno/hitl/queue.py` | `ReviewQueue.propose_merge` / `decide` — merge needs a tap |
| `apps/core/src/juno/bot/review.py` | `/review` + callback handler (`rev:{id}:approve\|reject\|skip`) |
| `apps/core/src/juno/bot/handlers.py` | Help text; re-exports review handlers |
| `apps/core/src/juno/runtime.py` | Registers `/review` + callback; attaches queue on `bot_data` |
| `apps/core/tests/test_review.py` | Merge stays pending until approve |
| `apps/core/tests/test_bot_review.py` | Keyboard, allowlist, callback commits |

Rules encoded in code:

- Writes go through `Database.write()` (ADR-02)
- `Edge.status` stays `pending` until Approve; Reject sets `rejected`; Skip does not commit
- Empty Telegram allowlist still rejects everyone
- Queue also reads `bot_data["juno"].db` so it can attach next to the #18–#19 `BotServices` object without owning that issue

### Docs

- This session file
- Codebase map + [`docs/next-work.md`](../next-work.md)

---

## Not in this session

- PR / merge to `main` (`Closes #20`)
- Auto-enqueue from ingest or RAG (nothing on `main` proposes merges yet; call `ReviewQueue.propose_merge`)
- `/digest` `/pause` `/status` (#19) — in progress on another worktree; `/review` is still marked "(coming)" there
- RAG answers (#17)
- Live Telegram smoke (#4)

---

## How to verify

From `apps/core`:

```powershell
$env:EMBEDDING_BACKEND="stub"
uv run pytest
uv run ruff check src tests
```

Expect **44** tests passing.

Manual (after `juno serve` with a bot token): send `/review`. With an empty queue the bot replies `Review queue empty.` Enqueue a merge in a Python shell against the same SQLite file via `ReviewQueue.propose_merge`, then `/review` again and tap Approve — the `edges` row should move to `committed`.

---

## Related docs

| File | Contents |
|------|----------|
| [08-session-hitl-review.md](08-session-hitl-review.md) | This file |
| [next-work.md](../next-work.md) | Global next-work tracker (kept as-is across merges) |
| [02-codebase-map.md](02-codebase-map.md) | HITL + bot review modules |
| [../../personal-knowledge-graph-prd.md](../../personal-knowledge-graph-prd.md) | §8 HITL layer |
