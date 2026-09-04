# ADR-07: Proactive jobs on the shared asyncio loop

## Status

Accepted (M4 / v1.3)

## Date

2026-09-04

## Context

M4 (epic [#27](https://github.com/Anna-Hax/JUNO/issues/27)) needs scheduled push (digests, resurfacing) without a second daemon. [ADR-01](001-shared-event-loop.md) already requires FastAPI + PTB + background work on **one** asyncio loop. `apscheduler` has been a declared dependency since M0; wiring was deferred until this milestone.

Options:

| Option | Summary | Why not (for v1.3) |
|--------|---------|---------------------|
| **A. BackgroundScheduler (thread)** | APScheduler thread pool next to uvicorn | Second loop/thread; SQLite session and PTB bot hazards |
| **B. Separate `juno jobs` process** | Cron-like sibling daemon | Breaks “one process is Juno”; Windows Startup story gets worse |
| **C. AsyncIOScheduler on the serve loop** | Lifespan start/stop; jobs are coroutines | **Chosen** |
| **D. APScheduler 4 AsyncScheduler** | New API (`add_schedule`) | Lock is 3.11.3; 4.x is a different package surface. Stay on 3.x until a dedicated upgrade. |

Juno already enforces:

- One serve process ([ADR-01](001-shared-event-loop.md))
- All DB writes through `Database.write()` ([ADR-02](002-sqlite-write-queue.md))
- Loopback + token auth for HTTP clients ([#21](https://github.com/Anna-Hax/JUNO/issues/21))
- Capture pause is a global override

## Decision

Run **`apscheduler.schedulers.asyncio.AsyncIOScheduler` (3.11)** inside `juno serve` lifespan, on the **same** event loop as uvicorn and PTB.

Concrete rules (`juno.jobs.scheduler`):

1. **Start** after PTB polling is up (jobs may `bot.send_message`). **Stop** (`shutdown(wait=False)`) before PTB shutdown.
2. Do **not** use `BackgroundScheduler` or a second OS process.
3. Push only to `ALLOWED_TELEGRAM_USER_IDS`. Empty allowlist → log and skip (same closed default as the bot).
4. Global `/pause` skips outbound job pushes (jobs must read `app.state.capture_paused`).
5. Config knobs (pydantic-settings / `.env`):
   - `JUNO_JOBS_ENABLED` (default `true`) — start the scheduler at all
   - `JUNO_JOBS_TIMEZONE` (default `UTC`) — cron/date interpretation
   - `JUNO_JOBS_SMOKE` (default `false`) — Spike S4 one-shot Telegram line ~2s after start
   - Per-job enable + 5-field crontab: `JUNO_JOBS_DIGEST_DAILY` / `_CRON` (default `true`, `0 7 * * *`), `JUNO_JOBS_DIGEST_WEEKLY` / `_CRON` (default `true`, `0 7 * * mon`), `JUNO_JOBS_RESURFACING` / `_CRON` (default `true`, `0 * * * *`), `JUNO_JOBS_POLISH` / `_CRON` (default `true`, `0 8 * * *`)
6. Tests and CI must not require live Telegram: `builtin_job_specs` / `register_job_specs` import and register without a bot; keep `JUNO_JOBS_SMOKE` off unless an operator is proving the loop.

Named jobs live in `juno.jobs.registry` (`digest_daily`, `digest_weekly`, `resurfacing`, `polish`). Invalid crontab fails at serve start (`CronTrigger.from_crontab`). Digest push bodies land in [#88](https://github.com/Anna-Hax/JUNO/issues/88). Resurfacing ([#89](https://github.com/Anna-Hax/JUNO/issues/89)) pushes high-confidence “this came up again” notes and queues low-confidence suggestions as HITL `resurface`. `module_health.jobs` records digest/resurface freshness ([#94](https://github.com/Anna-Hax/JUNO/issues/94)). `module_health.polish` records flashcard/draft generation ticks ([#114](https://github.com/Anna-Hax/JUNO/issues/114)); `/pause` skips generation and does not push draft text.

## Consequences

### Positive

- One mental model: if `juno serve` is up, scheduled work can run; if the PC is off, nothing pushes (honest with local-first).
- Jobs share `Database`, PTB `bot`, and pause flag without IPC.
- Operator can prove the loop with `JUNO_JOBS_SMOKE=true` without waiting for a morning cron.

### Negative / constraints

- A blocking job freezes HTTP + Telegram together — same ADR-01 rule; use `asyncio.to_thread` for CPU.
- Smoke push will message every allowlisted id once per serve start when enabled — leave it off after Spike S4.
- APScheduler 4 is explicitly out of scope until lock + API are upgraded together.

## Spike S4 proof

Issue [#86](https://github.com/Anna-Hax/JUNO/issues/86): `AsyncIOScheduler` date job fires on `asyncio.get_running_loop()`; `send_allowlisted_push` is the Telegram path (see [session 39](../sessions/39-session-spike-s4.md)).

## Scaffold (#87)

Issue [#87](https://github.com/Anna-Hax/JUNO/issues/87): `builtin_job_specs` + `register_job_specs` on the serve loop; CI registers cron jobs without sending Telegram (see [session 40](../sessions/40-session-jobs-scaffold.md)).

## Module health (#94)

Issue [#94](https://github.com/Anna-Hax/JUNO/issues/94): `module_health.jobs` is written through `Database.write()` on scheduler start and after each digest/resurfacing tick (including `/pause` skips). Last success/error shows on Telegram `/status` and `GET /status.modules`.

## Polish jobs (#114)

Issue [#114](https://github.com/Anna-Hax/JUNO/issues/114): named cron `polish` queues HITL flashcard drafts (and a journal draft if none is pending). It does **not** auto-publish or Telegram-push draft bodies. `/pause` records `module_health.polish` as skipped and generates nothing.

## What landed (M4)

- Named cron jobs: daily/weekly digest push ([#88](https://github.com/Anna-Hax/JUNO/issues/88)), contextual resurfacing with HITL fallback ([#89](https://github.com/Anna-Hax/JUNO/issues/89)).
- Telegram `/jobs` toggles persist via `AppSetting` (`jobs.enabled.{id}`).
- CI covers scheduler registration, digest/resurface bodies, and pause skips **without** live Telegram (`JUNO_JOBS_SMOKE` stays off).
- Gate: [`docs/v1.3-release-gate.md`](../v1.3-release-gate.md).
