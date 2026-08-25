# Session log: HITL review queue (#20)

**Date:** 2026-08-26  
**Repo:** [https://github.com/Anna-Hax/JUNO](https://github.com/Anna-Hax/JUNO)  
**Plan:** Personal Knowledge Graph (local-first Python + Telegram)  
**Scope of this session:** M1 issue **#20** — `review_items` queue + Telegram `/review` inline Approve / Reject / Skip.

---

## Summary

Proposed graph merges now land as a `pending` edge plus a `review_items` row. They do not become `committed` until an allowlisted user taps **Approve**. `/review` shows the oldest open item with inline buttons; Reject leaves the edge unapplied; Skip keeps it in the queue.

This branch was rebased onto `main` after PRs **#32–#34** (#14/#15, #17, #18/#19). `/review` is registered next to the merged bot commands and uses `BotServices` / `user_allowed`.

Work is on branch `feat/hitl-review`. PR / `Closes #20` not opened yet.

---

## What changed

### Code

| Path | Role |
|------|------|
| `apps/core/src/juno/hitl/queue.py` | `ReviewQueue.propose_merge` / `decide` — merge needs a tap |
| `apps/core/src/juno/bot/review.py` | `/review` + callback handler (`rev:{id}:approve\|reject\|skip`) |
| `apps/core/src/juno/bot/handlers.py` | Help text lists Approve / Reject / Skip |
| `apps/core/src/juno/runtime.py` | Registers `/review` + callback; attaches `ReviewQueue` beside `BotServices` |
| `apps/core/tests/test_review.py` | Merge stays pending until approve |
| `apps/core/tests/test_bot_review.py` | Keyboard, allowlist, callback commits |

Rules encoded in code:

- Writes go through `Database.write()` (ADR-02)
- `Edge.status` stays `pending` until Approve; Reject sets `rejected`; Skip does not commit
- Empty Telegram allowlist still rejects everyone (`user_allowed`)
- Queue prefers `bot_data["review"]`, else `BotServices.db` from `bot_data["juno"]`

### Docs

- This session file (numbered **10** so it does not collide with `08-session-rag.md`)
- Codebase map + [`docs/next-work.md`](../next-work.md)

---

## Not in this session

- PR / merge to `main` (`Closes #20`)
- Auto-enqueue from ingest or RAG (call `ReviewQueue.propose_merge`)
- Live Telegram smoke (#4)

---

## How to verify

From `apps/core`:

```powershell
$env:EMBEDDING_BACKEND="stub"
uv run pytest
uv run ruff check src tests
```

Expect **88** tests passing.

Manual (after `juno serve` with a bot token): send `/review`. With an empty queue the bot replies `Review queue empty.` Enqueue a merge via `ReviewQueue.propose_merge`, then `/review` again and tap Approve — the `edges` row should move to `committed`.

---

## Related docs

| File | Contents |
|------|----------|
| [10-session-hitl-review.md](10-session-hitl-review.md) | This file |
| [09-session-telegram-bot.md](09-session-telegram-bot.md) | Merged #18 / #19 bot |
| [next-work.md](../next-work.md) | Global next-work tracker (kept as-is across merges) |
| [02-codebase-map.md](02-codebase-map.md) | HITL + bot review modules |
| [../../personal-knowledge-graph-prd.md](../../personal-knowledge-graph-prd.md) | §8 HITL layer |
