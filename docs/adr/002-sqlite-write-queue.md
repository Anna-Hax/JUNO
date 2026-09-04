# ADR-02: SQLite write serialization

## Status

Accepted (v1)

## Date

2026-08-20 (M0 scaffold)  
**Last reviewed:** 2026-08-26 (after M1 / issue #12)

## Context

Multiple producers write the knowledge graph in one process:

- FastAPI `POST /ingest`
- Inbox watcher (`InboxWatcher` → `IngestPipeline`)
- Telegram capture handlers (forward / URL / document)
- HITL review decisions (`ReviewQueue.decide`)
- Runtime persistence (pause flag, embedder settings, module health)
- Later: scheduled jobs (M4)

SQLite allows only one writer at a time. On Windows especially, concurrent writers surface as `database is locked` / `OperationalError`, which is unacceptable for a personal agent that must keep ingesting while the user queries from Telegram.

We already commit to **one asyncio event loop** ([ADR-01](001-shared-event-loop.md)). That means we can serialize writers with an in-process lock instead of inventing a multi-process write broker for v1.

## Options considered

| Option | Summary | Why not (for v1) |
|--------|---------|------------------|
| **A. Ignore it** | Let SQLAlchemy sessions write freely | Locks under concurrent inbox + bot + API |
| **B. Separate write process / queue service** | Redis, dedicated writer worker | Overkill for local-first single-user v1 |
| **C. WAL + `busy_timeout` only** | Rely on SQLite retries | Helps, but overlapping writers still contend and can fail under burst ingest |
| **D. WAL + `busy_timeout` + asyncio write lock** | One `Database.write()` gate for all commits | **Chosen** |

## Decision

Use **SQLite WAL mode**, a non-zero **busy timeout**, and a **single asyncio write lock** around every mutating transaction.

Concrete rules (implemented in `apps/core/src/juno/graph/db.py`):

1. On connect (and after migrate / `create_all`), set `PRAGMA journal_mode=WAL` and `PRAGMA busy_timeout=5000`.
2. Expose **`Database.write(fn)`** — acquires `asyncio.Lock`, opens a session, begins a transaction, runs `fn(session)`, commits.
3. Expose **`Database.read(fn)`** — opens a session **without** the write lock so reads can proceed while a write is held (subject to SQLite WAL semantics).
4. **All** graph mutations go through `db.write(...)`. Callers must not open ad-hoc write sessions for commits. Known writers today: ingest pipeline, HITL queue, bot pause persistence, runtime health / embedder settings.
5. `Database.journal_mode()` exists so tests can assert WAL is actually on after migrate.

Acceptance for [#12](https://github.com/Anna-Hax/JUNO/issues/12): concurrent ingest must not lock. Covered by `apps/core/tests/test_write_queue.py` (many overlapping `IngestPipeline.ingest_text` calls via `asyncio.gather`, plus a read-during-write check).

## Consequences

### Positive

- Concurrent producers (bot + inbox + API) share one safe write path.
- Personal-scale write throughput (one transaction at a time) is fine.
- Reads stay available enough for `/search`, digests, and `/status` while a write is in flight.
- Tests can prove the acceptance criterion without flaky “hope SQLite retries”.

### Negative / constraints

- Write throughput is intentionally limited; a pathological burst of huge ingest jobs will queue behind the lock.
- Long-running work **inside** `db.write` holds the lock — keep write callbacks short (flush ORM rows; do PDF/HTML/Chroma work outside the lock, as the ingest pipeline already does).
- Forgetting `db.write` and committing on a raw session reintroduces lock risk; code review should treat that as a bug.

### Follow-ups

- M4 jobs ([ADR-07](007-proactive-jobs-shared-loop.md)) must use the same `Database.write` path — do not add a second writer. Spike S4 (#86) only sends Telegram; digest/resurfacing writes stay on this queue.
- If a future milestone needs true multi-process writers (e.g. a separate capture helper), revisit this ADR; WAL alone will not be enough across processes without a stronger coordination story.
