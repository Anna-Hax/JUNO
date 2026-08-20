# ADR-01: Shared asyncio event loop (FastAPI + Telegram)

## Status
Accepted (v1)

## Context
Juno must run a localhost FastAPI server and a Telegram long-polling bot in one
local-first process. `Application.run_polling()` is a blocking wrapper and
cannot share an event loop with uvicorn.

## Decision
- Run uvicorn via `uvicorn.Server.serve()` inside `asyncio.run`.
- Manage python-telegram-bot with `initialize` → `start` → `updater.start_polling`
  inside FastAPI lifespan; shut down in reverse on exit.
- Never call `Application.run_polling()`.

## Consequences
Bot and API share one process and one loop. Watcher and APScheduler must also
be asyncio tasks, not separate threads with their own loops.
