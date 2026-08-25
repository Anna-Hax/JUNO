# Session log: Telegram query + capture + pause/digest/status (#18 / #19)

**Date:** 2026-08-26  
**Repo:** [https://github.com/Anna-Hax/JUNO](https://github.com/Anna-Hax/JUNO)  
**Plan:** Personal Knowledge Graph (local-first Python + Telegram)  
**Scope of this session:** M1 issues **#18** (allowlist + `/start` `/help` + text query) and **#19** (forward-to-capture + `/digest` `/pause` `/resume` `/status`).

---

## Summary

Allowlisted users get real replies: questions go through the merged #17 RAG engine (`juno.rag.engine.search` — sourced answer when the LLM is healthy, retrieve-only otherwise). Strangers get silence. Forwards, bare http(s) links, and document attachments ingest as `source_type=telegram`. `/pause` persists to `settings.capture_paused` and stops inbox, `POST /ingest`, and Telegram capture; `/resume` clears the flag and scans the inbox backlog. `/digest today|week` lists recent captures; `/status` live-probes LLM health like `GET /status`.

Work is on branch `feat/telegram-bot-18-19` (from `main`, including PRs #32 and #33). PR / `Closes #18` `#19` not opened yet.

---

## What changed

### Code

| Path | Role |
|------|------|
| `apps/core/src/juno/bot/services.py` | Allowlist, pause persistence, digest/status/query formatting |
| `apps/core/src/juno/bot/handlers.py` | Commands + text/document handlers |
| `apps/core/src/juno/runtime.py` | Register commands; inject `BotServices`; load pause on startup; pass chat into `create_app` |
| `apps/core/tests/test_bot.py` | Allowlist, query, capture, pause vs API 423, digest, status |

Rules encoded in code:

- Empty allowlist still rejects everyone (secure default); strangers are not answered
- Plain text = query; forward / single URL / document = capture
- `/pause` is capture-only — queries still work
- Pause is stored in SQLite `settings` so it survives restart
- `/resume` calls `InboxWatcher.scan_existing()` for files dropped while paused
- Query uses merged `juno.rag.engine.search` (`GET /search` is the same engine)

### Docs

- This session file
- Codebase map + [`docs/next-work.md`](../next-work.md) + README command line

---

## Not in this session

- PR / merge to `main` (`Closes #18` / `#19`)
- HITL `/review` inline buttons (#20)
- Voice / photo OCR capture (later milestones)
- Live Telegram smoke (#4)

---

## How to verify

From `apps/core`:

```powershell
$env:EMBEDDING_BACKEND="stub"
uv run pytest
uv run ruff check src tests
```

Expect the full suite green (foundation + ingest + vectors + embedder + chat + rag + bot).

Manual (after `juno serve` with token + allowlist):

- Unknown Telegram user: no reply
- Allowlisted `/start` then a question: retrieve-only or sourced answer
- Forward a note or send a URL: capture ack
- `/pause` then `POST /ingest` → 423; `/resume` then inbox files process

---

## Related docs

| File | Contents |
|------|----------|
| [09-session-telegram-bot.md](09-session-telegram-bot.md) | This file |
| [08-session-rag.md](08-session-rag.md) | M1 #17 RAG ([PR #33](https://github.com/Anna-Hax/JUNO/pull/33)) |
| [06-session-ingest.md](06-session-ingest.md) | M1 #16 ingest |
| [next-work.md](../next-work.md) | Global next-work tracker |
