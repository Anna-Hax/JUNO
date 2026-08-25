# Codebase map (as of M0 / early M1)

**Last updated:** 2026-08-22

---

## Top level

```
JUNO/
  apps/core/          # Python agent (source of truth for v1)
  apps/extension/     # Browser capture stub (Phase 2)
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
| CLI | `cli.py` | `juno serve` / `db-init` / `version` |
| Runtime | `runtime.py` | Shared asyncio: uvicorn + PTB + inbox watcher lifespan |
| API | `api/__init__.py` | FastAPI routes + token + loopback middleware |
| Bot | `bot/handlers.py` | Telegram commands / text stub |
| Graph DB | `graph/db.py`, `graph/migrations.py` | Engine, WAL, write queue, Alembic upgrade/stamp |
| Vectors | `graph/vectors.py` | Persistent Chroma; one collection per embedding model ([ADR-04](../adr/004-chroma-collections.md)) — on #13 branch |
| Models | `models/__init__.py` | SQLAlchemy tables |
| Alembic | `alembic/` + `alembic.ini` | Revision `0001` = current ORM ([ADR-03](../adr/003-alembic.md)) |
| LLM | `llm/embedder.py`, `llm/chat.py` | Embeddings + chat providers |
| Ingest | `ingest/extractors.py`, `chunking.py`, `pipeline.py`, `watcher.py` | File/URL extract, chunk, persist, inbox watch ([#16](https://github.com/Anna-Hax/JUNO/issues/16)) |
| Jobs | `jobs/` | Placeholder (M4) |

### Entry points

- `uv run juno serve` → `runtime.main_sync()`
- `uv run juno db-init` → `Database.migrate()` (Alembic `upgrade head`, or stamp legacy `create_all` DBs)
- Tests: `apps/core/tests/test_foundation.py`, `test_migrations.py`, `test_ingest.py` (`test_vectors.py` on the #13 branch)

### Dependencies

Declared in `apps/core/pyproject.toml` + lockfile `uv.lock`.  
Optional: `--extra embeddings` for sentence-transformers; `--extra dev` for pytest/ruff.

---

## Extension stub

- `apps/extension/manifest.json` — MV3, host permission for `127.0.0.1`
- `apps/extension/background.js` — log-only placeholder

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
5. API token required even on localhost.
6. Stub embedder so CI never downloads torch.
7. Chroma collections are per embedding model; Juno supplies embeddings (no Chroma default ONNX). Blocking Chroma I/O uses `asyncio.to_thread`.
