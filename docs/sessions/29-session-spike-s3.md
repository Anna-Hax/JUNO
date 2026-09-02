# Session 29 — Spike S3 (#64)

**Date:** 2026-09-02  
**Issue:** [#64](https://github.com/Anna-Hax/JUNO/issues/64) — Spike S3: Cursor state.vscdb / exporter POST /ingest smoke  
**Epic:** [#26](https://github.com/Anna-Hax/JUNO/issues/26)  
**Branch:** `feat/spike-s3-64`

## Decision

In-tree **read-only** wrapper of Cursor's `composerHeaders` + `composerData:` / `bubbleId:` keys (not vendoring cursor-chat-export / cursor-session). Adapter is a loopback HTTP client. Recorded in [ADR-06](../adr/006-ide-adapter-client.md).

## What changed

- `apps/ide/cursor_vscdb.py` — read-only exporter; skip empty tool bubbles.
- `apps/ide/smoke.py` — `discover` / `export --latest --post`.
- [ADR-06](../adr/006-ide-adapter-client.md); pytest fixture covers parse + `POST /ingest` `source_type=ide`.

## Smoke

```powershell
cd apps/core
uv run juno serve
# other terminal, repo root, token from .env:
python apps/ide/smoke.py discover
python apps/ide/smoke.py export --latest --post
```

Confirm `GET /search?q=<title>` with Bearer returns the capture.

## Deferred to #65+

Package layout + config paths + CI, idempotent chat sync, terminal errors, HITL, retrieval, digests, module health, M3 gate.

## Links

| Doc | Role |
|-----|------|
| [006-ide-adapter-client.md](../adr/006-ide-adapter-client.md) | ADR |
| [next-work.md](../next-work.md) | M3 queue + issue numbers |
