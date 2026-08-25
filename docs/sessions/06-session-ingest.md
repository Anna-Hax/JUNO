# Session log: ingest pipeline + inbox watcher (#16)

**Date:** 2026-08-22  
**Repo:** [https://github.com/Anna-Hax/JUNO](https://github.com/Anna-Hax/JUNO)  
**Plan:** Personal Knowledge Graph (local-first Python + Telegram)  
**Scope of this session:** M1 issue **#16** — extractors (txt/md/pdf/url), ingest pipeline, inbox watcher.

---

## Summary

Dropping a file into `inbox/` (or `POST /ingest`) now creates a `captures` row plus `chunks`. Unreadable PDFs are stored as `status=failed` with `error_reason`, not silently skipped. The watcher runs as an asyncio task on the shared serve loop (ADR-01); watchdog only posts paths onto a queue.

Work is on branch `feat/ingest-pipeline` (from `main`). PR / `Closes #16` not opened yet.

---



## What changed



### Code


| Path                                      | Role                                                                       |
| ----------------------------------------- | -------------------------------------------------------------------------- |
| `apps/core/src/juno/ingest/extractors.py` | txt/md, PDF (PyMuPDF), HTML (trafilatura), `.url` shortcuts, http(s) fetch |
| `apps/core/src/juno/ingest/chunking.py`   | Overlapping character chunks                                               |
| `apps/core/src/juno/ingest/pipeline.py`   | Extract → chunk → `db.write` (ADR-02) → optional vector upsert             |
| `apps/core/src/juno/ingest/watcher.py`    | Inbox Observer → asyncio queue; archive to `.processed` / `.failed`        |
| `apps/core/src/juno/api/__init__.py`      | `/ingest` persists via the pipeline                                        |
| `apps/core/src/juno/runtime.py`           | Starts/stops watcher in FastAPI lifespan                                   |
| `apps/core/tests/test_ingest.py`          | Drop file, bad PDF, URL mock, API, pause                                   |


Rules encoded in code:

- Writes go through `Database.write()` (ADR-02)
- PDF/HTML CPU work and Chroma (when attached) stay off the serve loop (`asyncio.to_thread`)
- Chunk ids are `c{capture_id}-n{ordinal}` so they can match `chunks.chroma_id` (ADR-04)
- Vector upsert is optional: `IngestPipeline(vectors=…)` when a `VectorStore` is attached; `juno serve` now passes the persistent Chroma wrapper (#13)
- Hidden / temp files (`.gitkeep`, `*.tmp`, `*.crdownload`) are ignored
- `/pause` is not wired yet; `app.state.capture_paused` already gates `/ingest` and the watcher



### Docs

- This session file
- Codebase map + [`docs/next-work.md`](../next-work.md) + README inbox line

---



## Not in this session

- PR / merge to `main` (`Closes #16`)
- RAG `/search` (#17)
- Telegram forward-to-capture (#19)
- Live Telegram smoke (#4) and Projects board (#9)

---



## How to verify

From `apps/core`:

```powershell
$env:EMBEDDING_BACKEND="stub"
uv run pytest
uv run ruff check src tests
```

Expect **24** tests passing (foundation + ingest + migrations).

Manual (after `juno serve`):

```powershell
# copy a markdown file into inbox/
copy .\README.md ..\..\inbox\note.md

# token from .env JUNO_API_TOKEN
curl -H "Authorization: Bearer <token>" -H "Content-Type: application/json" `
  -d "{\"source_type\":\"upload\",\"text\":\"hello inbox\"}" `
  http://127.0.0.1:8787/ingest
```

A good drop moves to `inbox/.processed/`. A corrupt `.pdf` becomes a failed capture and is moved to `inbox/.failed/`.

---



## Related docs


| File                                                                 | Contents                             |
| -------------------------------------------------------------------- | ------------------------------------ |
| [06-session-ingest.md](06-session-ingest.md)                         | This file                            |
| [05-session-alembic.md](05-session-alembic.md)                       | M1 #11 Alembic                       |
| [04-session-chroma-client.md](04-session-chroma-client.md)           | M1 #13 Chroma (other branch)         |
| [next-work.md](../next-work.md)                                     | Global next-work tracker (kept as-is across merges) |
| [02-codebase-map.md](02-codebase-map.md)                             | Ingest modules on the map            |
| [../adr/001-shared-event-loop.md](../adr/001-shared-event-loop.md)   | Watcher must share the serve loop    |
| [../adr/002-sqlite-write-queue.md](../adr/002-sqlite-write-queue.md) | All ingest writes through `db.write` |
| [../adr/004-chroma-collections.md](../adr/004-chroma-collections.md) | Chunk ids / vector upsert            |


