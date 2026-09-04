# Next work

**Last updated:** 2026-09-05  
**Track issues on:** [https://github.com/Anna-Hax/JUNO/issues](https://github.com/Anna-Hax/JUNO/issues)  
**Package:** `1.3.0` (M4 complete — M5 polish expanded; [`docs/v1.3-release-gate.md`](v1.3-release-gate.md))

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

---

## Unlock M3 (planning)

Epic: [#26](https://github.com/Anna-Hax/JUNO/issues/26) — *Epic: M3 IDE / Cursor capture (v1.2)*.  
Milestone: [M3: v1.2 IDE Capture](https://github.com/Anna-Hax/JUNO/milestone/9).

**Child issues expanded 2026-09-02** (#64–#73). Prefer one issue ≈ one PR.

| Order | Issue | Title |
| ----- | ----- | ----- |
| 1 | [#64](https://github.com/Anna-Hax/JUNO/issues/64) | Spike S3 — Cursor state.vscdb / exporter POST /ingest smoke — ✅ [session 29](sessions/29-session-spike-s3.md) |
| 2 | [#65](https://github.com/Anna-Hax/JUNO/issues/65) | IDE adapter scaffold — wrap exporter, config paths, CI — ✅ [session 30](sessions/30-session-ide-scaffold.md) |
| 3 | [#66](https://github.com/Anna-Hax/JUNO/issues/66) | Chat/composer bubbles — ingest Cursor sessions via /ingest — ✅ [session 31](sessions/31-session-ide-chat.md) |
| 4 | [#67](https://github.com/Anna-Hax/JUNO/issues/67) | Terminal error capture from IDE sessions — ✅ [session 32](sessions/32-session-ide-errors.md) |
| 5 | [#68](https://github.com/Anna-Hax/JUNO/issues/68) | HITL — confirm IDE error-match / review sensitive chat batches — ✅ [session 33](sessions/33-session-ide-hitl.md) |
| 6 | [#69](https://github.com/Anna-Hax/JUNO/issues/69) | Error-matching retrieval — have I seen this error before? — ✅ [session 34](sessions/34-session-error-match.md) |
| 7 | [#70](https://github.com/Anna-Hax/JUNO/issues/70) | Cross-reference IDE captures vs browser + inbox — ✅ [session 35](sessions/35-session-ide-crossref.md) |
| 8 | [#71](https://github.com/Anna-Hax/JUNO/issues/71) | Digest enrichment — IDE chats/errors in /digest today\|week — ✅ [session 36](sessions/36-session-ide-digest.md) |
| 9 | [#72](https://github.com/Anna-Hax/JUNO/issues/72) | Module health — ide sync freshness in /status + respect /pause — ✅ [session 37](sessions/37-session-ide-health.md) |
| 10 | [#73](https://github.com/Anna-Hax/JUNO/issues/73) | M3 gate — IDE tests, ADR, README, v1.2 release gate — ✅ [session 38](sessions/38-session-m3-gate.md) |

**First coding task:** #64–#72 ✅. M3 gate ([#73](https://github.com/Anna-Hax/JUNO/issues/73)) — ✅ [session 38](sessions/38-session-m3-gate.md).

### M3 design constraints (do not violate)

1. One process, one loop ([ADR-01](adr/001-shared-event-loop.md)) — IDE adapter is a **client**, not a second daemon.
2. All DB writes through `Database.write()` ([ADR-02](adr/002-sqlite-write-queue.md)).
3. Schema changes = new Alembic revision ([ADR-03](adr/003-alembic.md)).
4. Vectors only via the serve-process `VectorStore` after ingest ([ADR-04](adr/004-chroma-collections.md)).
5. Loopback + token auth only ([#21](https://github.com/Anna-Hax/JUNO/issues/21)) — never bind `0.0.0.0` for the adapter.
6. HITL: error-match reuse and sensitive chat batches stay reviewable ([#68](https://github.com/Anna-Hax/JUNO/issues/68), [#20](https://github.com/Anna-Hax/JUNO/issues/20) patterns).

---

## M3 — **complete** (2026-09-02)

Epic [#26](https://github.com/Anna-Hax/JUNO/issues/26) closed; milestone [M3: v1.2 IDE Capture](https://github.com/Anna-Hax/JUNO/milestone/9) complete. Gate: [`docs/v1.2-release-gate.md`](v1.2-release-gate.md).

---

## Unlock M4 (planning)

Epic: [#27](https://github.com/Anna-Hax/JUNO/issues/27) — *Epic: M4 Proactive + mobile depth (v1.3)*.  
Milestone: [M4: v1.3 Proactive & Mobile](https://github.com/Anna-Hax/JUNO/milestone/10).

**Child issues expanded 2026-09-04** (#86–#95). Prefer one issue ≈ one PR.

| Order | Issue | Title |
| ----- | ----- | ----- |
| 1 | [#86](https://github.com/Anna-Hax/JUNO/issues/86) | Spike S4 — APScheduler on shared loop + one Telegram push smoke — ✅ [session 39](sessions/39-session-spike-s4.md) |
| 2 | [#87](https://github.com/Anna-Hax/JUNO/issues/87) | Scheduler scaffold — APScheduler in serve lifespan + job registry — ✅ [session 40](sessions/40-session-jobs-scaffold.md) |
| 3 | [#88](https://github.com/Anna-Hax/JUNO/issues/88) | Scheduled push digests — morning daily + weekly — ✅ [session 41](sessions/41-session-jobs-digest.md) |
| 4 | [#89](https://github.com/Anna-Hax/JUNO/issues/89) | Contextual resurfacing — push when something comes up again — ✅ [session 42](sessions/42-session-jobs-resurface.md) |
| 5 | [#90](https://github.com/Anna-Hax/JUNO/issues/90) | Temporal queries — how has my understanding of X evolved — ✅ [session 43](sessions/43-session-temporal.md) |
| 6 | [#91](https://github.com/Anna-Hax/JUNO/issues/91) | Voice memos — Telegram voice → transcription → ingest — ✅ [session 44](sessions/44-session-voice.md) |
| 7 | [#92](https://github.com/Anna-Hax/JUNO/issues/92) | Mobile depth — phone captures via Telegram + sensitive HITL — ✅ [session 45](sessions/45-session-mobile-hitl.md) |
| 8 | [#93](https://github.com/Anna-Hax/JUNO/issues/93) | PC-off / serve-down status for operators — ✅ [session 46](sessions/46-session-serve-down.md) |
| 9 | [#94](https://github.com/Anna-Hax/JUNO/issues/94) | Module health — jobs scheduler freshness + respect /pause — ✅ [session 47](sessions/47-session-jobs-health.md) |
| 10 | [#95](https://github.com/Anna-Hax/JUNO/issues/95) | M4 gate — jobs tests, ADR, README, v1.3 release gate — ✅ [session 48](sessions/48-session-m4-gate.md) |

**First coding task:** #86–#95 ✅. M4 complete.

### M4 design constraints (do not violate)

1. One process, one loop ([ADR-01](adr/001-shared-event-loop.md)) — APScheduler on the **same** asyncio loop as uvicorn + PTB; no second daemon.
2. All DB writes through `Database.write()` ([ADR-02](adr/002-sqlite-write-queue.md)).
3. Schema changes = new Alembic revision ([ADR-03](adr/003-alembic.md)).
4. Vectors only via the serve-process `VectorStore` after ingest ([ADR-04](adr/004-chroma-collections.md)).
5. Push jobs respect allowlist + global `/pause`; never bind `0.0.0.0` for capture clients.
6. Sensitive mobile / voice batches stay HITL-reviewable ([#92](https://github.com/Anna-Hax/JUNO/issues/92), [#20](https://github.com/Anna-Hax/JUNO/issues/20) patterns).

### Explicitly **not** M4 (keep in later epics)

| Epic | Milestone | Scope |
| ---- | --------- | ----- |
| [#28](https://github.com/Anna-Hax/JUNO/issues/28) | M5 v2 polish | Flashcards, drafts, trust dial, Slack |

---

## M4 — **complete** (2026-09-04)

Epic [#27](https://github.com/Anna-Hax/JUNO/issues/27) closed; milestone [M4: v1.3 Proactive & Mobile](https://github.com/Anna-Hax/JUNO/milestone/10) complete. Gate: [`docs/v1.3-release-gate.md`](v1.3-release-gate.md).

---

## Before M5 — **complete** (2026-09-05)

No blocking prep tickets (unlike Before M2’s Spike S1 / board / protection). M4 milestone already closed; branch protection and the [JUNO Roadmap](https://github.com/users/Anna-Hax/projects/1) board remain in place. Closed leftover [M0: Project Setup & CI](https://github.com/Anna-Hax/JUNO/milestone/1) (0 open, 10 closed). ADRs current through M4 ([ADR-07](adr/007-proactive-jobs-shared-loop.md), [ADR-08](adr/008-voice-transcription.md)).

---

## Unlock M5 (planning)

Epic: [#28](https://github.com/Anna-Hax/JUNO/issues/28) — *Epic: M5 v2.0 polish*.  
Milestone: [M5: v2.0 Polish & Extensions](https://github.com/Anna-Hax/JUNO/milestone/11).

**Child issues expanded 2026-09-05** (#106–#115). Prefer one issue ≈ one PR.

| Order | Issue | Title |
| ----- | ----- | ----- |
| 1 | [#106](https://github.com/Anna-Hax/JUNO/issues/106) | Spike S5 — one auto-generated draft through HITL — ✅ [session 49](sessions/49-session-spike-s5.md) |
| 2 | [#107](https://github.com/Anna-Hax/JUNO/issues/107) | Draft artifacts scaffold — draft kinds + never auto-publish — ✅ [session 50](sessions/50-session-draft-scaffold.md) |
| 3 | [#108](https://github.com/Anna-Hax/JUNO/issues/108) | Flashcards / spaced repetition from highlights |
| 4 | [#109](https://github.com/Anna-Hax/JUNO/issues/109) | Auto-drafted dev journal / README drafts |
| 5 | [#110](https://github.com/Anna-Hax/JUNO/issues/110) | Skill-gap tracking |
| 6 | [#111](https://github.com/Anna-Hax/JUNO/issues/111) | Trust dial — per-category auto-commit thresholds |
| 7 | [#112](https://github.com/Anna-Hax/JUNO/issues/112) | Optional Slack forward into upload space |
| 8 | [#113](https://github.com/Anna-Hax/JUNO/issues/113) | Prune-with-confirm — retention / destructive graph cleanup |
| 9 | [#114](https://github.com/Anna-Hax/JUNO/issues/114) | Module health — polish jobs freshness + respect /pause |
| 10 | [#115](https://github.com/Anna-Hax/JUNO/issues/115) | M5 gate — polish tests, ADR, README, v2.0 release gate |

**First coding task:** #106–#107 ✅. Next: flashcards / SRS ([#108](https://github.com/Anna-Hax/JUNO/issues/108)).

### M5 design constraints (do not violate)

1. One process, one loop ([ADR-01](adr/001-shared-event-loop.md)) — flashcard/SRS/draft jobs on the **same** asyncio loop; no second daemon.
2. All DB writes through `Database.write()` ([ADR-02](adr/002-sqlite-write-queue.md)).
3. Schema changes = new Alembic revision ([ADR-03](adr/003-alembic.md)).
4. Vectors only via the serve-process `VectorStore` after ingest ([ADR-04](adr/004-chroma-collections.md)).
5. Auto-generated artifacts stay HITL drafts until approve — never auto-publish ([#107](https://github.com/Anna-Hax/JUNO/issues/107), [#20](https://github.com/Anna-Hax/JUNO/issues/20) patterns).
6. Destructive prune always requires confirm ([#113](https://github.com/Anna-Hax/JUNO/issues/113)). Slack is opt-in forward into the existing inbox — not a live workspace listener ([#112](https://github.com/Anna-Hax/JUNO/issues/112)).

### Explicitly **not** M5 (keep deferred)

| Item | Why |
| ---- | --- |
| Live Slack workspace bot / passive listener | PRD §6.3 non-goal; #112 is opt-in forward only |
| Rabbit-hole session narrative (A→B→C) | PRD §6.1 P1 browser; not in epic #28 |
| Write drafts into user git repos unattended | #109 requires confirm before any file write |

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