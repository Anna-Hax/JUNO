# Session log: M0 bootstrap execution

**Date:** 2026-08-20  
**Repo:** [https://github.com/Anna-Hax/JUNO](https://github.com/Anna-Hax/JUNO)  
**Plan:** Personal Knowledge Graph (local-first Python + Telegram)  
**Scope of this session:** Execute M0 (scaffold, CI, GitHub hygiene) and land early M1 foundation stubs.

---

## Summary

Greenfield repo went from **PRD-only** to a **runnable scaffold** on `main`, with CI green, milestones/labels/issues on GitHub, and ADRs for the riskiest architecture choices. The Projects v2 board was **not** created yet (needs `gh auth refresh` with `project` scope).

---

## What was created

### Repository layout


| Path                                      | Purpose                                    |
| ----------------------------------------- | ------------------------------------------ |
| `apps/core/`                              | Python package `juno` (uv + hatchling)     |
| `apps/core/src/juno/`                     | Runtime, API, bot, graph DB, LLM, models   |
| `apps/core/tests/`                        | Foundation tests (6 passing)               |
| `apps/extension/`                         | Chrome MV3 stub (Phase 2)                  |
| `inbox/`                                  | Drop folder for future ingest (`.gitkeep`) |
| `docs/adr/`                               | Architecture decision records              |
| `scripts/`                                | GitHub bootstrap scripts                   |
| `.github/workflows/`                      | CI + PR checks + project automation stub   |
| `.env.example`, `README.md`, `.gitignore` | Setup / privacy / local-first notes        |




### Core code (early M1 stubs)

- **Shared event loop runtime** (`juno/runtime.py`) — FastAPI via uvicorn + Telegram PTB manual lifecycle (no `run_polling()`). See ADR-01.
- **SQLite + WAL + async write lock** (`juno/graph/db.py`). See ADR-02.
- **ORM models** — captures, nodes, edges, chunks, review_items, module_health, settings.
- **CLI** — `juno serve`, `juno db-init`, `juno version`.
- **API** — loopback-oriented `/health`, token-gated `/status`, `/ingest`, `/search`.
- **Bot handlers** — `/start`, `/help`, plain-text stub; allowlist via `ALLOWED_TELEGRAM_USER_IDS`.
- **LLM** — Ollama + OpenAI-compat adapters; stub hash embedder for CI; sentence-transformers factory for local use.
- **Alembic** — placeholder only (`create_all` for now). See ADR-03.



### Documentation / ADRs

- [001-shared-event-loop.md](../adr/001-shared-event-loop.md)
- [002-sqlite-write-queue.md](../adr/002-sqlite-write-queue.md)
- [003-alembic.md](../adr/003-alembic.md)



### GitHub Actions


| Workflow                 | Role                                                        |
| ------------------------ | ----------------------------------------------------------- |
| `ci-python.yml`          | ruff + pytest on ubuntu & windows                           |
| `ci-extension.yml`       | manifest/background sanity (path-filtered)                  |
| `pr-checks.yml`          | conventional PR title + `Closes #` / `Refs #`               |
| `project-automation.yml` | auto-add to board when `PROJECT_PAT` + `PROJECT_NUMBER` set |


**Verified:** `CI Python` succeeded on the first push to `main`.

### GitHub project management

- **Labels:** type / area / priority / epic / blocked / needs-design / …
- **Milestones:** M0 → M5 (v1.0 foundation through v2.0 polish)
- **Issues:** 28 created (M0 + M1 concrete + M2–M5 epics)
- **Closed as done this session:** #1–3, #5–8, #10
- **Still open (M0):** #4 (live Telegram smoke), #9 (Projects board)



### Commits pushed

1. `6cc278f` — Bootstrap JUNO M0 scaffold with local-first Python core, CI, and ADRs
2. `eebae30` — Add project board bootstrap script for GitHub Projects v2

---



## Tooling installed on the machine

- `uv` 0.12.5 (`C:\Users\hp\.local\bin`)
- GitHub CLI `gh` 2.97.0
- `gh` authenticated as **Anna-Hax** (repo scopes); **project** scopes still missing

---



## Not finished in this session

1. **GitHub Projects board (“JUNO Roadmap”)** — blocked on:
  ```powershell
   gh auth refresh -h github.com -s project,read:project
   .\scripts\bootstrap-project.ps1
  ```
2. **Live Spike S1** with a real Telegram token (runtime code exists; end-to-end smoke is issue #4).
3. **Full M1 features** — Chroma wiring, inbox watcher, RAG answers, HITL Telegram UI, export/wipe (issues #11–24).
4. **Alembic first revision** — still using `create_all`.
5. **Branch protection** on `main` — not enabled in repo settings yet.

---



## How to run what exists

```powershell
cd D:\Juno\JUNO\apps\core
uv sync --extra dev
copy ..\..\.env.example ..\..\.env
# Edit .env: TELEGRAM_BOT_TOKEN, ALLOWED_TELEGRAM_USER_IDS, JUNO_API_TOKEN
uv run juno db-init
uv run juno serve
# Tests:
$env:EMBEDDING_BACKEND="stub"
uv run pytest
uv run ruff check src tests
```

---



## Related docs in this folder


| File                                                     | Contents                                                    |
| -------------------------------------------------------- | ----------------------------------------------------------- |
| [00-session-m0-bootstrap.md](00-session-m0-bootstrap.md) | This file — what was done in the first execute session      |
| [01-github-setup.md](01-github-setup.md)                 | Labels, milestones, issues, board, CI (how + current state) |
| [02-codebase-map.md](02-codebase-map.md)                 | Map of packages/modules and what each does                  |
| [next-work.md](../next-work.md)                         | Ordered next tasks (global; kept as-is across merges)       |
| [04-session-chroma-client.md](04-session-chroma-client.md) | M1 #13 Chroma persistent client                             |
| [05-session-alembic.md](05-session-alembic.md)             | M1 #11 first Alembic revision                               |
| [06-session-ingest.md](06-session-ingest.md)               | M1 #16 ingest pipeline + inbox watcher                      |


Update these files as later sessions land work, or add `06-session-….md` for new execute sessions.