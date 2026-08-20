# Codebase map (as of M0 / early M1 scaffold)

**Last updated:** 2026-08-20

---

## Top level

```
JUNO/
  apps/core/          # Python agent (source of truth for v1)
  apps/extension/     # Browser capture stub (Phase 2)
  inbox/              # Manual upload drop zone (watcher not wired)
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
| Runtime | `runtime.py` | Shared asyncio: uvicorn + PTB lifespan |
| API | `api/__init__.py` | FastAPI routes + token + loopback middleware |
| Bot | `bot/handlers.py` | Telegram commands / text stub |
| Graph DB | `graph/db.py` | Engine, WAL, write queue |
| Models | `models/__init__.py` | SQLAlchemy tables |
| LLM | `llm/embedder.py`, `llm/chat.py` | Embeddings + chat providers |
| Ingest | `ingest/` | Placeholder (M1) |
| Jobs | `jobs/` | Placeholder (M4) |

### Entry points

- `uv run juno serve` → `runtime.main_sync()`
- `uv run juno db-init` → `Database.create_all()`
- Tests: `apps/core/tests/test_foundation.py`

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
| `data/chroma/` | Planned vector store (not fully wired) |
| `inbox/` | Future watched uploads |
| `.env` | Secrets (never commit) |

---

## Design constraints already encoded

1. One process, one asyncio loop (ADR-01).
2. Serialized SQLite writes (ADR-02).
3. Migrations via Alembic when schema churns (ADR-03); scaffold still uses `create_all`.
4. Empty Telegram allowlist ⇒ reject all users (secure default).
5. API token required even on localhost.
6. Stub embedder so CI never downloads torch.
