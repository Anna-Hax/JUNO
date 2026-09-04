# ADR-01: Shared asyncio event loop (FastAPI + Telegram)

## Status

Accepted (v1)

## Date

2026-08-20 (M0 scaffold)  
**Last reviewed:** 2026-09-04 (M4 Spike S4 / ADR-07)

## Context

Juno is a **local-first** personal knowledge-graph agent. In v1 it must run on the user’s PC as a single always-on (or login-started) process that simultaneously:

1. Serves a **loopback FastAPI** API (`127.0.0.1`) for health, status, ingest, and search.
2. Runs a **Telegram bot** via long polling so the user can capture and query from their phone.
3. Hosts **background work** on the same process — inbox watching today, scheduled / proactive jobs later — without a second daemon.

Those pieces all need I/O concurrency. The natural fit in Python is one **asyncio** event loop. The friction is how to combine **uvicorn** (FastAPI) with **python-telegram-bot (PTB)**.

PTB’s convenience entrypoint `Application.run_polling()`:

- Blocks the calling thread.
- Owns (or expects to own) the asyncio lifecycle.
- Does not compose cleanly with `uvicorn.run()` / another long-lived server on the same loop.

If we used `run_polling()` in one thread and uvicorn in another, we would get **two event loops**, cross-thread session hazards, and awkward shutdown. If we ran two OS processes (API vs bot), we would duplicate config, complicate “is Juno up?”, and fight the local-first “one process you start from Startup” model.

## Options considered

| Option | Summary | Why not (for v1) |
|--------|---------|------------------|
| **A. Two processes** (uvicorn + `run_polling`) | Separate API and bot | Extra process management, shared state harder, worse Windows keep-alive story |
| **B. Threads with separate loops** | Bot thread + API thread | Dual loops; locking across SQLAlchemy async sessions; harder lifespan |
| **C. Shared loop, manual PTB lifecycle** | uvicorn `Server.serve()` + PTB `initialize` / `start` / `start_polling` inside FastAPI lifespan | **Chosen** |
| **D. Webhooks instead of polling** | Telegram pushes to a public URL | Needs a public endpoint; conflicts with loopback-only privacy defaults |

## Decision

Run **one process, one asyncio event loop**, shared by FastAPI, the Telegram bot, and all in-process background work.

Concrete rules (implemented in `apps/core/src/juno/runtime.py`):

1. **Entry** is `asyncio.run(run_server())` via `juno serve` (or bare `juno` with no subcommand).
2. Start the HTTP server with **`uvicorn.Server.serve()`** (awaitable), not a blocking `uvicorn.run()` that fights the outer loop.
3. Build the PTB `Application` normally, but **never** call `Application.run_polling()`.
4. Inside FastAPI **lifespan**:
   - **Startup:** `await ptb.initialize()` → `await ptb.start()` → `await ptb.updater.start_polling(...)`
   - **Shutdown (reverse):** jobs scheduler → inbox watcher → `updater.stop()` → `ptb.stop()` → `ptb.shutdown()`, then dispose the DB.
5. **All background work** on this process must be asyncio tasks, lifespan-managed objects, or async-compatible schedulers on **this same loop** — not a second “main” loop in another thread. That includes:
   - The inbox watcher (`InboxWatcher`, landed in M1 / #16)
   - APScheduler proactive jobs on this loop ([ADR-07](007-proactive-jobs-shared-loop.md); Spike S4 / #86)
   - Chroma I/O via `VectorStore` async helpers ([ADR-04](004-chroma-collections.md))
6. If `TELEGRAM_BOT_TOKEN` is empty, the API (and inbox watcher) still run and the bot is simply disabled — same process model either way.
7. Before listen, `validate_serve_settings()` refuses a non-loopback bind and the example API token ([#21](https://github.com/Anna-Hax/JUNO/issues/21)).

Blocking CPU work (PDF extract, embeddings, Chroma sync APIs) must use `asyncio.to_thread` (or the wrappers that already do) so HTTP and Telegram polling stay responsive.

## Consequences

### Positive

- One mental model: “Juno is up” means one process answers `/health` and (when configured) polls Telegram.
- Shared in-memory handles (`Database`, `VectorStore`, embedder, chat provider, `IngestPipeline`, `ReviewQueue`) without IPC.
- Clean shutdown path through FastAPI lifespan.
- Matches Windows Startup-folder shortcut: one `uv run juno serve` command.
- Inbox drops and API ingest share the same pause flag and write queue as the bot.

### Negative / constraints

- Everything long-running must play by asyncio rules; accidental blocking work freezes the bot and the API together.
- PTB and uvicorn upgrade notes must be checked together — lifecycle APIs are the integration surface.
- You cannot casually call `run_polling()` in scripts or tests without recreating the dual-loop problem; tests should mock handlers or exercise the manual lifecycle.
- On Windows, open Chroma clients hold file locks under `data/chroma/` — stop `juno serve` before `juno wipe` ([ADR-04](004-chroma-collections.md) / #23).

### What landed (M1)

- Inbox watcher started/stopped in the same lifespan as the bot ([#16](https://github.com/Anna-Hax/JUNO/issues/16)).
- Telegram query / capture / pause / digest / status / HITL review all registered on that PTB application ([#18](https://github.com/Anna-Hax/JUNO/issues/18)–[#20](https://github.com/Anna-Hax/JUNO/issues/20)).
- Chroma access goes through `VectorStore.upsert_async` / `query_async` ([ADR-04](004-chroma-collections.md)).

### Live Spike S1 (#4, 2026-08-29)

Confirmed on a real Windows machine with repo-root `.env`:

- `juno serve` loads settings via parent `.env` discovery (`resolve_env_file` / `get_settings`) so `cd apps/core` matches the documented quick start.
- `GET /health` → `{"status":"ok"}` without a token; `GET /status` → 401 without Bearer, 200 with `JUNO_API_TOKEN`.
- Telegram bot token + allowlist load; PTB `start_polling` runs inside the FastAPI lifespan on the **same** asyncio loop (no second-loop crash). Outbound `sendMessage` to the allowlisted user succeeded; bot identity verified via `getMe`.
- Optional: `POST /ingest` + `GET /search` round-trip committed a capture.

Operator may still tap `/start`, a short query, and `/status` in Telegram for full UX confirm while `juno serve` is up.

### Follow-ups (not M1)

- **APScheduler** on this loop landed in M4 ([ADR-07](007-proactive-jobs-shared-loop.md); [#86](https://github.com/Anna-Hax/JUNO/issues/86)–[#89](https://github.com/Anna-Hax/JUNO/issues/89), [#94](https://github.com/Anna-Hax/JUNO/issues/94)).
- Keep documenting “no `run_polling()`” next to any new entrypoint so this ADR is not rediscovered the hard way.
- IDE / Cursor capture is a **loopback HTTP client** ([ADR-06](006-ide-adapter-client.md)), not a second process or event loop.
