# ADR-09: Auto-generated artifacts stay HITL drafts

## Status

Accepted (M5 / Spike S5)

## Date

2026-09-05

## Context

PRD §8 P1: auto-generated artifacts (dev journals, README drafts, flashcards) land in a **draft/review** state — the operator skims, edits, and approves rather than the agent auto-publishing. Epic [#28](https://github.com/Anna-Hax/JUNO/issues/28) / Spike [#106](https://github.com/Anna-Hax/JUNO/issues/106) needs one proven path before a fuller scaffold ([#107](https://github.com/Anna-Hax/JUNO/issues/107)).

Options:

| Option | Summary | Why not (for v2 spike) |
|--------|---------|------------------------|
| **A. LLM body on every serve** | Call Ollama/OpenAI to write the paragraph | CI and offline operators cannot prove HITL; flakes |
| **B. Template snippet + HITL `draft` kind** | Deterministic text from recent capture titles; queue as `review_items` | **Chosen** |
| **C. Write a markdown file under `inbox/` or a git repo** | Operator sees a file immediately | Auto-publish by another name; #109 forbids unattended repo writes |
| **D. Push the draft to Telegram as canonical** | Looks like a digest | Treats generated text as committed knowledge |

## Decision

1. **Generation for Spike S5 is template-only** (`JUNO_DRAFTS_GENERATOR=template`). An LLM path may be added later for journal/README quality ([#109](https://github.com/Anna-Hax/JUNO/issues/109)); CI must still enqueue/decide without a live model.
2. Drafts are **`review_items` rows** with `kind=draft`. They are pending until Approve / Reject / Skip via existing `/review` ([#20](https://github.com/Anna-Hax/JUNO/issues/20)).
3. **Approve confirms; it does not publish.** Payload keeps `published=false`. No new `captures` row, no inbox file, no Telegram “canonical” post.
4. **Reject discards** (`discarded=true`); still not published. Skip leaves the item in the queue.
5. Writes go through `Database.write()` ([ADR-02](002-sqlite-write-queue.md)). Draft jobs, when scheduled, stay on the serve asyncio loop ([ADR-01](001-shared-event-loop.md), [ADR-07](007-proactive-jobs-shared-loop.md)).
6. Config knobs:
   - `JUNO_DRAFTS_SMOKE` (default `false`) — enqueue one journal snippet at serve start (Spike S5)
   - `JUNO_DRAFTS_GENERATOR` (default `template`) — ignored values other than `template` still use the template in S5
7. Global `/pause` skips smoke enqueue.

## Consequences

- Operators prove the HITL path with `JUNO_DRAFTS_SMOKE=true` then `/review` — no live LLM.
- Later kinds (flashcard / doc) reuse the same `draft` kind + payload `draft_kind` discriminator ([#107](https://github.com/Anna-Hax/JUNO/issues/107)).
- Publishing (file write, ingest, Telegram canonical) is a later, explicit confirm step — never a side effect of Approve in S5.

## Spike S5 proof

Issue [#106](https://github.com/Anna-Hax/JUNO/issues/106): template journal from recent captures (or a placeholder if none) lands pending; Approve/Reject/Skip work; `published` stays false (see [session 49](../sessions/49-session-spike-s5.md)).
