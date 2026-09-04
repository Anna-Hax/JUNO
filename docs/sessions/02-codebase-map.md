# Codebase map (as of M0 / early M1)

**Last updated:** 2026-09-04

---

## Top level

```
JUNO/
  apps/core/          # Python agent (source of truth for v1)
  apps/extension/     # Browser capture (M2 / ADR-05)
  apps/ide/           # Cursor vscdb HTTP client (M3 / ADR-06)
  inbox/              # Manual upload drop zone (watched by juno serve)
  data/               # Runtime DB/vectors (gitignored)
  docs/adr/           # Architecture decisions
  docs/sessions/      # What we did / how GitHub is set up / next work
  scripts/            # gh bootstrap helpers
  .github/            # Actions + PR template
  personal-knowledge-graph-prd.md
  README.md
  .env.example
```

---

## `apps/core` package (`juno`)

| Module | File(s) | Role |
|--------|---------|------|
| Config | `config.py` | pydantic-settings from `.env` |
| CLI | `cli.py` | `juno serve` / `db-init` / `export` / `wipe` / `version` |
| Runtime | `runtime.py` | Shared asyncio: uvicorn + PTB + inbox watcher + jobs scheduler lifespan |
| Jobs | `jobs/scheduler.py`, `jobs/registry.py`, `jobs/handlers.py`, `jobs/health.py`, `jobs/resurface.py` | AsyncIOScheduler + named cron registry (ADR-07) |
| API | `api/__init__.py` | FastAPI routes + token + loopback middleware |
| Bot | `bot/handlers.py`, `bot/services.py`, `bot/review.py` | Telegram allowlist, query, capture, pause/digest/status ([#18](https://github.com/Anna-Hax/JUNO/issues/18) / [#19](https://github.com/Anna-Hax/JUNO/issues/19)); HITL `/review` ([#20](https://github.com/Anna-Hax/JUNO/issues/20)) |
| Graph DB | `graph/db.py`, `graph/migrations.py`, `graph/ownership.py` | Engine, WAL, write queue, Alembic upgrade/stamp; export/wipe ([#23](https://github.com/Anna-Hax/JUNO/issues/23)) |
| Vectors | `graph/vectors.py` | Persistent Chroma; one collection per embedding model ([ADR-04](../adr/004-chroma-collections.md)) |
| Models | `models/__init__.py` | SQLAlchemy tables |
| Alembic | `alembic/` + `alembic.ini` | Revision `0001` = current ORM ([ADR-03](../adr/003-alembic.md)) |
| LLM | `llm/embedder.py`, `llm/chat.py`, `llm/transcribe.py` | MiniLM (optional extra) + stub embedder; Ollama / OpenAI-compat / offline chat; opt-in voice STT (ADR-08) |
| Ingest | `ingest/extractors.py`, `chunking.py`, `pipeline.py`, `watcher.py` | File/URL extract, chunk, persist, inbox watch ([#16](https://github.com/Anna-Hax/JUNO/issues/16)) |
| RAG | `rag/engine.py` | Vector retrieve, join captures, sourced answer + confidence ([#17](https://github.com/Anna-Hax/JUNO/issues/17)); Telegram query uses this |
| HITL | `hitl/queue.py` | Review queue; merges stay pending until Approve ([#20](https://github.com/Anna-Hax/JUNO/issues/20)) |

### Entry points

- `uv run juno serve` → `runtime.main_sync()`
- `uv run juno db-init` → `Database.migrate()` (Alembic `upgrade head`, or stamp legacy `create_all` DBs)
- Tests: `test_foundation.py`, `test_migrations.py`, `test_ingest.py`, `test_vectors.py`, `test_embedder.py`, `test_chat.py`, `test_rag.py`, `test_bot.py`, `test_review.py`, `test_bot_review.py`, `test_api.py`, `test_write_queue.py`, `test_integration.py`, `test_export.py`, `test_jobs.py`, `test_transcribe.py`

### Dependencies

Declared in `apps/core/pyproject.toml` + lockfile `uv.lock`.  
Optional: `--extra embeddings` for sentence-transformers; `--extra dev` for pytest/ruff.

---

## Extension (M2)

- `apps/extension/` — MV3 loopback client ([ADR-05](../adr/005-browser-extension-client.md))

## IDE adapter (M3 / Spike S3)

- `apps/ide/cursor_vscdb.py` — read-only Cursor `state.vscdb` wrapper
- `apps/ide/config.py` / `api.py` / `sync.py` — env paths, loopback HTTP, poll/watch ([ADR-06](../adr/006-ide-adapter-client.md))

---

## Data on disk (local-first)

| Path | Contents |
|------|----------|
| `data/juno.db` | SQLite graph (after `db-init` / serve) |
| `data/chroma/` | Persistent Chroma collections (one per embedding model) |
| `inbox/` | Watched uploads; processed files go to `inbox/.processed/` (failed → `inbox/.failed/`) |
| `.env` | Secrets (never commit) |

---

## Design constraints already encoded

1. One process, one asyncio loop (ADR-01).
2. Serialized SQLite writes (ADR-02).
3. Migrations via Alembic (ADR-03); `db-init` / serve run `upgrade head` (stamp pre-Alembic files).
4. Empty Telegram allowlist ⇒ reject all users (secure default).
5. API token required even on localhost. Empty / `change-me` never authorize; `juno serve` refuses a non-loopback bind. `/docs` is disabled ([#21](https://github.com/Anna-Hax/JUNO/issues/21)).
6. Stub embedder so CI never downloads torch; MiniLM is `--extra embeddings`. `/status` reports the live backend (and `embedding_fallback` if serve dropped to stub).
7. Chroma collections are per embedding model; Juno supplies embeddings (no Chroma default ONNX). Blocking Chroma I/O uses `asyncio.to_thread`.
8. Chat adapters switch on `LLM_PROVIDER` (`ollama` / `openai_compat` / `offline`). `/status` live-probes `llm_healthy` + provider/model. Unhealthy LLM ⇒ retrieve-only (#17).
9. Proposed merges stay `pending` until a Telegram Approve tap ([#20](https://github.com/Anna-Hax/JUNO/issues/20)).
