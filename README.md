# JUNO

Personal knowledge-graph agent: passively (and manually) capture what you read, code, and discuss — query it from **Telegram**. Local-first on your PC.

**Status:** M1 — local API + Telegram query/capture/HITL. Not a daily driver yet.

## Architecture (v1)

- **Python core** (`apps/core`): FastAPI on `127.0.0.1` + Telegram long-polling in one shared asyncio event loop ([ADR-01](docs/adr/001-shared-event-loop.md))
- **SQLite + write queue** for the graph ([ADR-02](docs/adr/002-sqlite-write-queue.md)); **Alembic** for schema changes ([ADR-03](docs/adr/003-alembic.md))
- **Chroma** for vectors — persistent client, one collection per embedding model ([ADR-04](docs/adr/004-chroma-collections.md)); **stub embedder** in CI
- **Browser extension** (`apps/extension`): stub until Phase 2
- **Inbox** (`inbox/`): drop `.txt` / `.md` / `.pdf` / `.url` (or a one-line http(s) text file). `juno serve` watches the folder; good files move to `inbox/.processed/`, unreadable PDFs to `inbox/.failed/`.
- **HITL** (`/review`): inline Approve / Reject / Skip for pending graph merges

## Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)
- Optional: [Ollama](https://ollama.com/) for local LLM answers
- Optional: Telegram bot token from [@BotFather](https://t.me/BotFather)

## Quick start

```powershell
cd apps/core
uv sync --extra dev
# Local MiniLM embeddings (optional; without this, serve falls back to the stub):
uv sync --extra dev --extra embeddings
copy ..\..\.env.example ..\..\.env   # from repo root: copy .env.example .env
# Edit .env: TELEGRAM_BOT_TOKEN, ALLOWED_TELEGRAM_USER_IDS, JUNO_API_TOKEN
uv run juno db-init
uv run juno serve
```

Data ownership:

```powershell
uv run juno export -o ../../data/backup.json
# Stop juno serve first on Windows, then:
uv run juno wipe --confirm wipe-all-data
```

- API: `http://127.0.0.1:8787/health` (no token). `/status` `/ingest` `/search` need `Authorization: Bearer <JUNO_API_TOKEN>`. Serve refuses the example `change-me` token and any non-loopback `JUNO_API_HOST`.
- Token-gated `GET /status` reports the live embedder (model / backend / dimensions) and LLM health (`llm_healthy`, `llm_provider`, `llm_model`). If Ollama is down, `llm_healthy` is false and answers stay retrieve-only.
- Token-gated `GET /search?q=` returns citations + confidence (sourced answer when the LLM is healthy).
- Bot runs only while this process (and PC) is on. Telegram queues updates ~24h; longer downtime can drop messages. Commands: `/start` `/help` `/digest today|week` `/pause` `/resume` `/status` `/review`. Forward a message, send a link, or attach a doc to capture; other text queries the graph.

### Tests

```powershell
cd apps/core
$env:EMBEDDING_BACKEND="stub"
uv run pytest
uv run ruff check src tests
```

## Privacy

- Data stays under `data/` on your machine.
- API is loopback-only and token-gated.
- Empty `ALLOWED_TELEGRAM_USER_IDS` rejects all Telegram users (configure your numeric user id).
- Do not commit `.env` or `data/`.

## Roadmap

See [personal-knowledge-graph-prd.md](personal-knowledge-graph-prd.md) and GitHub milestones M0→M5 (v1.0 foundation → v2.0 polish).

**Next work:** [docs/next-work.md](docs/next-work.md) (living queue; kept as-is across branch merges).  
**Session docs** (what was built, GitHub setup, codebase map): [docs/sessions/](docs/sessions/).

## Windows keep-alive

Create a Startup-folder shortcut to:

```powershell
uv run --directory D:\Juno\JUNO\apps\core juno serve
```

so Juno comes back after login. This is not a service; sleep/shutdown still pauses capture.
