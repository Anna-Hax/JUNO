# ADR-01: Shared asyncio event loop (FastAPI + Telegram)

## Status

Accepted (v1)

## Date

2026-08-20 (M0 scaffold)

## Context

Juno is a **local-first** personal knowledge-graph agent. In v1 it must run on the user’s PC as a single always-on (or login-started) process that simultaneously:

1. Serves a **loopback FastAPI** API (`127.0.0.1`) for health, status, ingest, and search.
2. Runs a **Telegram bot** via long polling so the user can capture and query from their phone.
3. Later hosts **inbox watching**, **scheduled jobs**, and other background work without a separate daemon.

Those pieces all need I/O concurrency. The natural fit in Python is one **asyncio** event loop. The friction is how to combine **uvicorn** (FastAPI) with **python-telegram-bot (python-tg-bot)**.

python-tg-bot’s convenience entrypoint `Application.run_polling()`:

- Blocks the calling thread.
- Owns (or expects to own) the asyncio lifecycle.
- Does not compose cleanly with `uvicorn.run()` / another long-lived server on the same loop.

If we used `run_polling()` in one thread and uvicorn in another, we would get **two event loops**, cross-thread session hazards, and awkward shutdown. If we ran two OS processes (API vs bot), we would duplicate config, complicate “is Juno up?”, and fight the local-first “one process you start from Startup” model.

## Options considered


| Option                                         | Summary                                                                                         | Why not (for v1)                                                              |
| ---------------------------------------------- | ----------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------- |
| **A. Two processes** (uvicorn + `run_polling`) | Separate API and bot                                                                            | Extra process management, shared state harder, worse Windows keep-alive story |
| **B. Threads with separate loops**             | Bot thread + API thread                                                                         | Dual loops; locking across SQLAlchemy async sessions; harder lifespan         |
| **C. Shared loop, manual python-tg-bot lifecycle**       | uvicorn `Server.serve()` + python-tg-bot `initialize` / `start` / `start_polling` inside FastAPI lifespan | Chosen                                                                        |
| **D. Webhooks instead of polling**             | Telegram pushes to a public URL                                                                 | Needs a public endpoint; conflicts with loopback-only privacy defaults        |




## Decision

Run **one process, one asyncio event loop**, shared by FastAPI and the Telegram bot.

Concrete rules:

1. Entry is `asyncio.run(run_server())` (see `juno/runtime.py` / `juno serve`).
2. Start the HTTP server with `uvicorn.Server.serve()` (awaitable), not a blocking `uvicorn.run()` that fights the outer loop.
3. Build the python-tg-bot `Application` normally, but **never** call `Application.run_polling()`.
4. Inside FastAPI **lifespan**:
  - startup: `await python-tg-bot.initialize()` → `await python-tg-bot.start()` → `await python-tg-bot.updater.start_polling(...)`
  - shutdown (reverse): `updater.stop()` → `python-tg-bot.stop()` → `python-tg-bot.shutdown()`
5. Future background work (inbox watcher, APScheduler jobs, Chroma maintenance) must be **asyncio tasks or async-compatible schedulers on this same loop**, not a second “main” loop in another thread.

If `TELEGRAM_BOT_TOKEN` is empty, the API still runs and the bot is simply disabled — same process model either way.

## Consequences



### Positive

- One mental model: “Juno is up” means one process answers `/health` and (when configured) polls Telegram.
- Shared in-memory handles (`Database`, embedder, chat provider) without IPC.
- Clean shutdown path through FastAPI lifespan.
- Matches Windows Startup-folder shortcut: one `uv run juno serve` command.



### Negative / constraints

- Everything long-running must play by asyncio rules; blocking CPU work needs `asyncio.to_thread` (or similar) so polling and HTTP stay responsive.
- python-tg-bot and uvicorn upgrade notes must be checked together — lifecycle APIs are the integration surface.
- You cannot casually call `run_polling()` in scripts or tests without recreating the dual-loop problem; tests should exercise the manual lifecycle or mock the bot.



### Follow-ups

- Wire inbox watcher and APScheduler as tasks on this loop (M1).
- Chroma access goes through `VectorStore` async helpers / `asyncio.to_thread` ([ADR-04](004-chroma-collections.md)).
- Keep documenting “no `run_polling()`” next to any new entrypoint so the ADR is not rediscovered the hard way.

