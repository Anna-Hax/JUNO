# Session log: WAL + write-queue acceptance (#12)

**Date:** 2026-08-26  
**Repo:** [https://github.com/Anna-Hax/JUNO](https://github.com/Anna-Hax/JUNO)  
**Plan:** Personal Knowledge Graph (local-first Python + Telegram)  
**Scope of this session:** M1 issue **#12** — WAL + async write-queue; acceptance: concurrent ingest does not lock.

---

## Summary

`Database.write()` already serialized commits with an `asyncio.Lock` (ADR-02) and connections already set `PRAGMA journal_mode=WAL` + `busy_timeout=5000`. This pass proves the acceptance: 24 overlapping `ingest_text` calls complete without `database is locked`, WAL is queryable, and reads proceed while a write is held.

Work landed on `main` via [PR #37](https://github.com/Anna-Hax/JUNO/pull/37) (`Closes #12`).

---

## What changed

### Code

| Path | Role |
|------|------|
| `apps/core/src/juno/graph/db.py` | `Database.journal_mode()` for WAL checks |
| `apps/core/tests/test_write_queue.py` | WAL pragma, concurrent ingest, read-during-write |

Ingest, HITL, bot pause, and runtime health already go through `db.write()` — no stray write sessions.

### Docs

- This session file
- ADR-02 consequences
- Codebase map + [`docs/next-work.md`](../next-work.md)

---

## Not in this session

- Integration tests (#22)
- Export / wipe (#23)

---

## How to verify

From `apps/core`:

```powershell
$env:EMBEDDING_BACKEND="stub"
uv run pytest
uv run ruff check src tests
```

Expect **103** tests passing.

---

## Related docs

| File | Contents |
|------|----------|
| [12-session-write-queue.md](12-session-write-queue.md) | This file |
| [11-session-api-harden.md](11-session-api-harden.md) | Merged #21 API |
| [../adr/002-sqlite-write-queue.md](../adr/002-sqlite-write-queue.md) | ADR-02 |
| [next-work.md](../next-work.md) | Global next-work tracker |
