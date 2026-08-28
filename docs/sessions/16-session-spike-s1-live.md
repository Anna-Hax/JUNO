# Session 16 — Live Spike S1 (#4)

**Date:** 2026-08-29  
**Issue:** [#4](https://github.com/Anna-Hax/JUNO/issues/4) — Spike S1: PTB + uvicorn shared event-loop hello-world  
**Branch:** `chore/spike-s1-live-4`

## What changed

- **`resolve_env_file` / `get_settings`** in `apps/core/src/juno/config.py` — walk cwd then parents for `.env` so the documented `cd apps/core` + repo-root `.env` quick start actually loads secrets (previously `juno serve` fell back to `change-me` and refused to start).
- Unit test for parent `.env` discovery.
- ADR-01 live-smoke section; README note; this session log; `docs/next-work.md` checklist update.

## Live smoke (this machine)

| Check | Result |
|-------|--------|
| `uv run juno db-init` | OK (alembic → 0001) |
| `uv run juno serve` | OK on `127.0.0.1:8787` (shared loop; PTB polling started) |
| `GET /health` (no token) | `{"status":"ok"}` |
| `GET /status` without Bearer | 401 |
| `GET /status` with Bearer | 200 (`capture_paused`, embedder, llm fields) |
| Telegram `getMe` | OK (`@JUNO_2006_bot`) |
| Outbound `sendMessage` to allowlisted user | OK |
| `POST /ingest` + `GET /search?q=Spike%20S1` | Capture committed; search returned it |

Notes:

- Ollama was down → `llm_healthy: false` (retrieve-only); expected.
- Embeddings used **stub** (no `--extra embeddings` in this smoke); MiniLM optional.
- Interactive Telegram `/start` + query + `/status` from the phone/desktop client: operator confirm while serve is up (bot already messaged the allowlist chat).

## Deferred

- Projects board (#9), branch protection, M1 milestone close — next Before-M2 items.
- MiniLM install / Ollama up — not required to close #4.

## How to verify

```powershell
cd apps/core
uv sync --extra dev
# ensure repo-root .env has real JUNO_API_TOKEN + Telegram token/allowlist
uv run juno db-init
uv run juno serve
# other shell:
Invoke-RestMethod http://127.0.0.1:8787/health
# GET /status with Authorization: Bearer <token>
# Telegram: /start, a short query, /status
```

## Links

| Doc | Role |
|-----|------|
| [001-shared-event-loop.md](../adr/001-shared-event-loop.md) | ADR-01 + live smoke |
| [next-work.md](../next-work.md) | Global board |
| [15-session-v1-release-gate.md](15-session-v1-release-gate.md) | Prior M1 gate |
