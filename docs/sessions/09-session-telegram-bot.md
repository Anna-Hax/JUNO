# Session log: Telegram query + capture + pause/digest/status (#18 / #19)

**Date:** 2026-08-26  
**Repo:** [https://github.com/Anna-Hax/JUNO](https://github.com/Anna-Hax/JUNO)  
**Plan:** Personal Knowledge Graph (local-first Python + Telegram)  
**Scope of this session:** M1 issues **#18** (allowlist + `/start` `/help` + text query) and **#19** (forward-to-capture + `/digest` `/pause` `/resume` `/status`).

---

## Summary

Allowlisted users get real replies: questions go through the #17 RAG engine (sourced answer when the LLM is healthy, retrieve-only otherwise). Strangers get silence. Forwards, bare http(s) links, and document attachments ingest as `source_type=telegram`. `/pause` persists to `settings.capture_paused` and stops inbox, `POST /ingest`, and Telegram capture; `/resume` clears the flag and scans the inbox backlog. `/digest today|week` lists recent captures; `/status` reports pause, LLM, embedder, Chroma, and `module_health`.

Work is on branch `feat/telegram-bot-18-19` (from `main`). PR / `Closes #18` `#19` not opened yet.

---

## What changed

### Code

| Path | Role |
|------|------|
| `apps/core/src/juno/bot/services.py` | Allowlist, pause persistence, digest/status/query formatting |
| `apps/core/src/juno/bot/handlers.py` | Commands + text/document handlers |
| `apps/core/src/juno/runtime.py` | Register commands; inject `BotServices`; load pause on startup |
| `apps/core/src/juno/rag/` | RAG engine from `feat/rag-retrieve` so Telegram query can cite |
| `apps/core/tests/test_bot.py` | Allowlist, query, capture, pause vs API 423, digest, status |

Rules encoded in code:

- Empty allowlist still rejects everyone (secure default); strangers are not answered
- Plain text = query; forward / single URL / document = capture
- `/pause` is capture-only — queries still work
- Pause is stored in SQLite `settings` so it survives restart
- `/resume` calls `InboxWatcher.scan_existing()` for files dropped while paused
- Query prefers `juno.rag.engine.search`; falls back to raw `VectorStore.query_async`

### Docs

- This session file
- Codebase map + [`docs/next-work.md`](../next-work.md) + README command line

---

## Not in this session

- PR / merge to `main` (`Closes #18` / `#19`)
- `GET /search` HTTP wiring (stays on `feat/rag-retrieve` / #17)
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

Expect **44** tests passing.

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
| [06-session-ingest.md](06-session-ingest.md) | M1 #16 ingest |
| `feat/rag-retrieve` | M1 #17 RAG engine (copied `juno.rag` from that branch) |
| [next-work.md](../next-work.md) | Global next-work tracker |
