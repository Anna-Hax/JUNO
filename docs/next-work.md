# Next work (after M0 bootstrap)

**Last updated:** 2026-08-26  
**Track issues on:** https://github.com/Anna-Hax/JUNO/issues

---

## M1 v1.0 foundation — **complete**

Gate: [`docs/v1.0-release-gate.md`](v1.0-release-gate.md) (issue **#24**, PR closes milestone).

| Issue | Work | PR |
|-------|------|-----|
| #11 | Alembic schema | (early M1) |
| #13 | Chroma client | [#29](https://github.com/Anna-Hax/JUNO/pull/29) |
| #16 | Ingest + inbox | [#31](https://github.com/Anna-Hax/JUNO/pull/31) |
| #14 / #15 | MiniLM + LLM health | [#32](https://github.com/Anna-Hax/JUNO/pull/32) |
| #17 | RAG + citations | [#33](https://github.com/Anna-Hax/JUNO/pull/33) |
| #18 / #19 | Telegram bot | [#34](https://github.com/Anna-Hax/JUNO/pull/34) |
| #20 | HITL `/review` | [#35](https://github.com/Anna-Hax/JUNO/pull/35) |
| #21 | API harden | [#36](https://github.com/Anna-Hax/JUNO/pull/36) |
| #12 | Write queue | [#37](https://github.com/Anna-Hax/JUNO/pull/37) |
| #22 | Integration tests | [#38](https://github.com/Anna-Hax/JUNO/pull/38) |
| #23 | Export / wipe | [#39](https://github.com/Anna-Hax/JUNO/pull/39) |
| #24 | Release gate | (this branch) |

**Next coding wave:** M2 browser capture — expand epic **#25** into split tickets.

---

## Do first (finish M0 ops)

1. **Projects board** (issue #9)
   ```powershell
   gh auth refresh -h github.com -s project,read:project
   .\scripts\bootstrap-project.ps1
   ```

2. **Live Spike S1** (issue #4) — fill `.env`, run `juno serve`, confirm Telegram `/start` + `GET /health` together.

3. **Branch protection** on `main` — require CI Python + PR Checks.

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

Keep this `docs/next-work.md` updated so the board and docs stay aligned.
Do not recreate `docs/sessions/03-next-work.md`. This file is kept as-is across branch merges.
