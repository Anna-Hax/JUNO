# ADR-06: IDE adapter as loopback HTTP client (Cursor vscdb)

## Status

Accepted (M3 / Spike S3)

## Date

2026-09-02

## Context

M3 needs Cursor chat (and later terminal errors) in the same graph as browser and inbox captures. The PRD asked to wrap an existing open-source exporter that reads local `state.vscdb` rather than inventing a Cursor API client.

Juno already enforces:

- One serve process ([ADR-01](001-shared-event-loop.md))
- No second Chroma/SQLite writer ([ADR-02](002-sqlite-write-queue.md), [ADR-04](004-chroma-collections.md))
- Loopback + Bearer token ([#21](https://github.com/Anna-Hax/JUNO/issues/21))
- Browser capture is already an HTTP client ([ADR-05](005-browser-extension-client.md))

## Exporter evaluation (Spike S3)

| Tool | Form | Fit |
|------|------|-----|
| [somogyijanos/cursor-chat-export](https://github.com/somogyijanos/cursor-chat-export) | Python CLI, workspace `state.vscdb` **tabs** | Outdated vs Cursor 3.x `composerHeaders` + `bubbleId:` keys; not a library |
| [vuil/cursor-session](https://github.com/vuil/cursor-session) | Go CLI | Extra runtime; subprocess; not pip-installable |
| [anasabbasdev/cursor-chat-bulk-export](https://github.com/anasabbasdev/cursor-chat-bulk-export) | VS Code extension | UI exporter, not an ingest library |
| [changlehu/cursor-chat-export-to-markdown](https://github.com/changlehu/cursor-chat-export-to-markdown) | Small Python script | Markdown dump only; no HTTP ingest |

None of these are a stable Python API we can depend on. They all reverse-engineer the same unofficial SQLite keys. Live probe on this machine (Cursor global `state.vscdb`, ~200 MB, `composerHeaders` table present) confirmed:

- Session index: `composerHeaders` (Cursor 3.x central index)
- Envelope: `cursorDiskKV` `composerData:{composerId}`
- Messages: `cursorDiskKV` `bubbleId:{composerId}:{bubbleId}` (`type` 1 = user, 2 = assistant; many type-2 rows are empty tool bubbles)

## Decision

Ship an **in-tree read-only wrapper** of that community schema (`apps/ide/cursor_vscdb.py`) plus a stdlib smoke CLI that `POST`s to loopback `/ingest`:

- Open Cursor's DB with SQLite URI `mode=ro` (copy-to-temp fallback if locked). **Never write** Cursor files.
- `source_type=ide`, `uri=cursor://composer/{id}`, chat text + `raw_json` session metadata.
- Adapter is an **HTTP client only** — same constraints as the MV3 extension. No second Juno daemon, no direct Chroma/SQLite.

Do **not** vendor a third-party exporter as a runtime dependency.

## Breakage risks

Cursor's storage is unofficial and has already migrated once (per-workspace `composer.composerData` → global `composerHeaders` in 3.0). If Cursor changes keys:

- `discover` returns 0 sessions or `load_session` yields empty bubbles.
- Guard missing fields; skip empty tool bubbles; do not assume `conversationMap` still holds text.
- Mitigation: keep a fixture `state.vscdb` in tests; bump the reader when a live discover fails; record the Cursor version in the session log.

Watch/poll, config paths, idempotent re-sync, terminal errors, HITL, and module health stay in later M3 issues (#65–#72).

## Consequences

### Positive

- Same ingest pipeline, write queue, and vectors as Telegram / inbox / browser.
- Schema changes stay server-side (Alembic).
- Tests do not need a live Cursor install (synthetic vscdb fixture).

### Negative

- We own schema drift instead of tracking an upstream CLI.
- User must run the client against a local `juno serve` (token + loopback).

## Spike S3 proof

Issue [#64](https://github.com/Anna-Hax/JUNO/issues/64): fixture + live `state.vscdb` export → `POST /ingest` with Bearer token (see [session 29](../sessions/29-session-spike-s3.md)).
