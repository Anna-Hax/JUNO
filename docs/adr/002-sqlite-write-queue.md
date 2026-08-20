# ADR-02: SQLite write serialization

## Status
Accepted (v1)

## Context
Multiple producers write the graph: Telegram handlers, inbox watcher, FastAPI
`/ingest`, and later scheduled jobs. Concurrent SQLite writers cause
`database is locked` errors on Windows.

## Decision
- Use SQLite WAL mode and `busy_timeout=5000`.
- Expose a single `Database.write()` method guarded by an `asyncio.Lock` so all
  commits are serialized.
- Reads may proceed without the write lock.

## Consequences
Write throughput is limited to one transaction at a time (fine for personal use).
Callers must use `db.write` / `db.read` instead of opening ad-hoc sessions for writes.
