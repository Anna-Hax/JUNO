# Next work (after M0 bootstrap)

**Last updated:** 2026-08-20  
**Track issues on:** https://github.com/Anna-Hax/JUNO/issues

---

## Do first (finish M0)

1. **Projects board** (issue #9)
   ```powershell
   gh auth refresh -h github.com -s project,read:project
   .\scripts\bootstrap-project.ps1
   ```
   Then set Status columns in the UI; optionally add `PROJECT_PAT` + `PROJECT_NUMBER` secrets.

2. **Live Spike S1** (issue #4) — fill `.env`, run `juno serve`, confirm Telegram `/start` + `GET /health` together.

3. **Branch protection** on `main` (repo Settings) — require CI Python + PR Checks.

---

## M1 implementation order (small PRs)

Prefer one open issue ≈ one PR (`Closes #N`).

| Order | Issue | Work |
|-------|-------|------|
| 1 | #13 | Chroma persistent client (collection per embedding model) |
| 2 | #11 | First Alembic revision (stop relying only on `create_all`) |
| 3 | #16 | Ingest pipeline + extractors + inbox watcher |
| 4 | #14 / #15 | Confirm MiniLM path + LLM health in `/status` |
| 5 | #17 | Retrieve-only → sourced RAG + confidence |
| 6 | #18–#19 | Bot query + forward-to-capture + digest/pause/status |
| 7 | #20 | HITL `/review` inline buttons |
| 8 | #21 | Harden API (already stubbed) |
| 9 | #22–#24 | Integration tests, export/wipe, v1.0 gate |

Already partially landed (keep issues open until acceptance fully met): #11 models/`db-init`, #12 write queue, #14 stub embedder, #15 chat adapters, #18 allowlist handlers, #21 basic routes.

---

## After v1.0

- Expand epic **#25** (M2 browser) into split tickets.
- Then #26 IDE, #27 proactive, #28 v2 polish — same wave pattern.

---

## When you finish a coding session

Add a new file: `docs/sessions/0N-session-<short-name>.md` describing:

- What changed (files / commits / issues closed)
- What broke or was deferred
- How to verify

Keep this `03-next-work.md` updated so the board and docs stay aligned.
