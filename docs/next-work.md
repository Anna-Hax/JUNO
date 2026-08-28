# Next work

**Last updated:** 2026-08-29  
**Track issues on:** [https://github.com/Anna-Hax/JUNO/issues](https://github.com/Anna-Hax/JUNO/issues)  
**Package:** `1.1.0` (M2 browser capture complete — [`docs/v1.1-release-gate.md`](v1.1-release-gate.md))

Prefer one open issue ≈ one PR (`Closes #N`). This file is kept as-is across branch merges (`merge=ours`).

---

## Before M2 (finish / unblock)

Do these **before or while starting** M2 coding. They are not blocked on the browser extension, but leaving them open means M2 work has no live smoke proof and a weaker board.  
Before this make sure that docs/adr are up to date.


| Order | Item                                                                                                                                                               | Issue                                                                         | Why                                                                                    |
| ----- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ----------------------------------------------------------------------------- | -------------------------------------------------------------------------------------- |
| 1     | **Live Spike S1** — ✅ done 2026-08-29 ([session 16](sessions/16-session-spike-s1-live.md)); optional interactive Telegram `/start` from the client while serve is up | [#4](https://github.com/Anna-Hax/JUNO/issues/4)                               | Proves ADR-01 on a real machine; M2 extension depends on the same loopback API + token |
| 2     | **Projects v2 board** — ✅ done 2026-08-29 ([session 17](sessions/17-session-projects-board.md)); board [#1](https://github.com/users/Anna-Hax/projects/1) + auto-add secrets | [#9](https://github.com/Anna-Hax/JUNO/issues/9)                               | M2 will create many tickets; board keeps Ready / In Progress / Done honest             |
| 3     | **Branch protection** on `main` — ✅ done 2026-08-29 ([session 18](sessions/18-session-before-m2-ops.md)) | (repo Settings)                                                               | Stops accidental direct pushes during the extension wave                               |
| 4     | **Close / note M1 milestone** — ✅ closed 2026-08-29 ([M1 milestone](https://github.com/Anna-Hax/JUNO/milestone/7)) | Milestone [M1: v1.0 Foundation](https://github.com/Anna-Hax/JUNO/milestone/7) | Hygiene only                                                                           |




### Spike S1 checklist (#4)

```powershell
cd apps/core
uv sync --extra dev
# Optional MiniLM: uv sync --extra dev --extra embeddings
copy ..\..\.env.example ..\..\.env   # then edit secrets — not change-me
uv run juno db-init
uv run juno serve
```

Confirm together:

- [x] `GET http://127.0.0.1:8787/health` → `{"status":"ok"}` (no token)
- [x] `GET /status` with `Authorization: Bearer …` → 200; without → 401
- [x] Telegram bot online on shared loop (`getMe` + outbound to allowlist); operator: `/start`, a text query, `/status` from the client
- [x] Optional: `POST /ingest` + `/search` (Spike S1 smoke capture)



### Projects board (#9)

```powershell
gh auth refresh -h github.com -s project,read:project
.\scripts\bootstrap-project.ps1   # idempotent — reuses JUNO Roadmap #1
```

Board: [JUNO Roadmap](https://github.com/users/Anna-Hax/projects/1). Secrets `PROJECT_PAT` + `PROJECT_NUMBER=1` set for `.github/workflows/project-automation.yml`.

---

## Before M2 — **complete** (2026-08-29)

All four prep items done. Next: expand epic [#25](https://github.com/Anna-Hax/JUNO/issues/25) and start M2 coding (Spike S2 first).

---



## Unlock M2 (planning, first coding day)

Epic only today: [#25](https://github.com/Anna-Hax/JUNO/issues/25) — *Epic: M2 Browser capture (v1.1)*.  
Milestone: [M2: v1.1 Browser Capture](https://github.com/Anna-Hax/JUNO/milestone/8).

**First coding task:** expand #25 into concrete child issues — **done 2026-08-29** (#44–#53).

| Order | Issue | Title |
| ----- | ----- | ----- |
| 1 | [#44](https://github.com/Anna-Hax/JUNO/issues/44) | Spike S2 — POST /ingest smoke |
| 2 | [#45](https://github.com/Anna-Hax/JUNO/issues/45) | MV3 scaffold — ✅ [session 20](sessions/20-session-mv3-scaffold.md) |
| 3 | [#46](https://github.com/Anna-Hax/JUNO/issues/46) | URL + title + timestamp — ✅ [session 21](sessions/21-session-browser-timestamp.md) |
| 4 | [#47](https://github.com/Anna-Hax/JUNO/issues/47) | Engagement metrics — ✅ [session 22](sessions/22-session-engagement-metrics.md) |
| 5 | [#48](https://github.com/Anna-Hax/JUNO/issues/48) | Highlights — ✅ [session 23](sessions/23-session-highlights.md) |
| 6 | [#49](https://github.com/Anna-Hax/JUNO/issues/49) | Domain excludes + pause — ✅ [session 24](sessions/24-session-domain-excludes.md) |
| 7 | [#50](https://github.com/Anna-Hax/JUNO/issues/50) | Module health — ✅ [session 25](sessions/25-session-module-health.md) |
| 8 | [#51](https://github.com/Anna-Hax/JUNO/issues/51) | Cross-reference — ✅ [session 26](sessions/26-session-cross-reference.md) |
| 9 | [#52](https://github.com/Anna-Hax/JUNO/issues/52) | Digest enrichment — ✅ [session 27](sessions/27-session-digest-enrichment.md) |
| 10 | [#53](https://github.com/Anna-Hax/JUNO/issues/53) | Extension tests + M2 gate — ✅ [session 28](sessions/28-session-m2-gate.md) |

Stub today: `apps/extension/` (MV3 manifest + service worker + options). Extension must talk **HTTP to the loopback API** — no second Chroma/SQLite client ([ADR-04](adr/004-chroma-collections.md), [ADR-05](adr/005-browser-extension-client.md)).

---

## M2 — **complete** (2026-08-29)

Epic [#25](https://github.com/Anna-Hax/JUNO/issues/25) closed; milestone [M2: v1.1 Browser Capture](https://github.com/Anna-Hax/JUNO/milestone/8) complete. Gate: [`docs/v1.1-release-gate.md`](v1.1-release-gate.md).

**Next:** epic [#26](https://github.com/Anna-Hax/JUNO/issues/26) — M3 IDE / Cursor capture.

---



## M2 implementation order (proposed small PRs)

PRD Phase 2 + epic #25: Spike S2, MV3, URL/title, metrics, highlights, excludes, digests.  
Prefer one issue ≈ one PR. Order is dependency-aware.


| Order | Proposed work                                                                                                                                | Notes / acceptance sketch                                                                                  |
| ----- | -------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------- |
| 1     | **Spike S2** ([#44](https://github.com/Anna-Hax/JUNO/issues/44)) — custom MV3 extension; prove one capture reaches `POST /ingest` with Bearer token             | [ADR-05](adr/005-browser-extension-client.md) + [session 19](sessions/19-session-spike-s2.md) |
| 2     | **MV3 scaffold** ([#45](https://github.com/Anna-Hax/JUNO/issues/45)) — ✅ [session 20](sessions/20-session-mv3-scaffold.md)   | Load unpacked extension; token stored locally; CI validates manifest + lib |
| 3     | **Capture URL + title + timestamp** ([#46](https://github.com/Anna-Hax/JUNO/issues/46)) — ✅ [session 21](sessions/21-session-browser-timestamp.md)                                                                    | Row in `captures`; shows up in `/search` / bot query                                                       |
| 4     | **Engagement metrics** ([#47](https://github.com/Anna-Hax/JUNO/issues/47)) — ✅ [session 22](sessions/22-session-engagement-metrics.md)                                                     | `raw_json.metrics`: active_time_ms, scroll_depth                                                         |
| 5     | **Highlights / selections** ([#48](https://github.com/Anna-Hax/JUNO/issues/48)) — ✅ [session 23](sessions/23-session-highlights.md)                                                                                                                  | Highlight text in `raw_json.highlights` + ingest text for search                                                   |
| 6     | **Domain / URL excludes** ([#49](https://github.com/Anna-Hax/JUNO/issues/49)) — ✅ [session 24](sessions/24-session-domain-excludes.md)                                                                                          | Options excludes; API 423 backs extension off; respects `/pause`                            |
| 7     | **Module health** ([#50](https://github.com/Anna-Hax/JUNO/issues/50)) — ✅ [session 25](sessions/25-session-module-health.md) | `extension` row in `module_health`; `GET /status.modules` + Telegram `/status`                         |
| 8     | **Cross-reference** ([#51](https://github.com/Anna-Hax/JUNO/issues/51)) — ✅ [session 26](sessions/26-session-cross-reference.md) browser captures vs upload/inbox content in retrieve / digest text                                                       | “You also uploaded notes on X” style citations or digest lines                                             |
| 9     | **Digest enrichment** ([#52](https://github.com/Anna-Hax/JUNO/issues/52)) — ✅ [session 27](sessions/27-session-digest-enrichment.md) — `/digest today|week` groups browser reading vs uploads/other                              | Scheduled *push* digests stay M4 unless explicitly pulled forward                                          |
| 10    | **Extension tests + docs** ([#53](https://github.com/Anna-Hax/JUNO/issues/53)) — ✅ [session 28](sessions/28-session-m2-gate.md) — `validate-extension.py`; v1.1 gate                              | CI green on `apps/extension/`                                                                            |




### M2 design constraints (do not violate)

1. One process, one loop ([ADR-01](adr/001-shared-event-loop.md)) — extension is a **client**, not a second daemon.
2. All DB writes through `Database.write()` ([ADR-02](adr/002-sqlite-write-queue.md)).
3. Schema changes = new Alembic revision ([ADR-03](adr/003-alembic.md)).
4. Vectors only via the serve-process `VectorStore` after ingest ([ADR-04](adr/004-chroma-collections.md)).
5. Loopback + token auth only ([#21](https://github.com/Anna-Hax/JUNO/issues/21)) — never bind `0.0.0.0` for the extension.
6. HITL: high-confidence URL visits may auto-commit; sensitive batches stay reviewable ([#20](https://github.com/Anna-Hax/JUNO/issues/20) patterns).



### Explicitly **not** M2 (keep in later epics)


| Epic                                              | Milestone             | Scope                                     |
| ------------------------------------------------- | --------------------- | ----------------------------------------- |
| [#26](https://github.com/Anna-Hax/JUNO/issues/26) | M3 IDE / Cursor       | Chat + terminal error capture             |
| [#27](https://github.com/Anna-Hax/JUNO/issues/27) | M4 Proactive + mobile | APScheduler push digests, voice, temporal |
| [#28](https://github.com/Anna-Hax/JUNO/issues/28) | M5 v2 polish          | Flashcards, drafts, trust dial, Slack     |


---



## M1 complete (reference)


| Issue     | Work                | PR                                              |
| --------- | ------------------- | ----------------------------------------------- |
| #11       | Alembic schema      | (early M1)                                      |
| #13       | Chroma client       | [#29](https://github.com/Anna-Hax/JUNO/pull/29) |
| #16       | Ingest + inbox      | [#31](https://github.com/Anna-Hax/JUNO/pull/31) |
| #14 / #15 | MiniLM + LLM health | [#32](https://github.com/Anna-Hax/JUNO/pull/32) |
| #17       | RAG + citations     | [#33](https://github.com/Anna-Hax/JUNO/pull/33) |
| #18 / #19 | Telegram bot        | [#34](https://github.com/Anna-Hax/JUNO/pull/34) |
| #20       | HITL `/review`      | [#35](https://github.com/Anna-Hax/JUNO/pull/35) |
| #21       | API harden          | [#36](https://github.com/Anna-Hax/JUNO/pull/36) |
| #12       | Write queue         | [#37](https://github.com/Anna-Hax/JUNO/pull/37) |
| #22       | Integration tests   | [#38](https://github.com/Anna-Hax/JUNO/pull/38) |
| #23       | Export / wipe       | [#39](https://github.com/Anna-Hax/JUNO/pull/39) |
| #24       | Release gate        | [#40](https://github.com/Anna-Hax/JUNO/pull/40) |


---



## When you finish a coding session

Add `docs/sessions/0N-session-<short-name>.md` with what changed, what deferred, how to verify.  
Update **this** file so the board and docs stay aligned.  
Do not recreate `docs/sessions/03-next-work.md`.