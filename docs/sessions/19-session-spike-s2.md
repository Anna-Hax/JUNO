# Session 19 — Spike S2 (#44)

**Date:** 2026-08-29  
**Issue:** [#44](https://github.com/Anna-Hax/JUNO/issues/44) — Spike S2: MV3 extension POST /ingest smoke  
**Epic:** [#25](https://github.com/Anna-Hax/JUNO/issues/25)  
**Branch:** `feat/spike-s2-44`

## Decision

Custom **MV3 extension** as loopback HTTP client (not History-only). Recorded in [ADR-05](../adr/005-browser-extension-client.md).

## What changed

- `apps/extension/`: service worker captures completed tabs → `POST /ingest` (`source_type=browser`, Bearer token).
- Minimal options/popup for API base URL + token (`chrome.storage.sync`).
- [ADR-05](../adr/005-browser-extension-client.md); M2 child issues #45–#53 created under epic #25.

## Smoke

With `juno serve` running and token saved in extension options:

1. Load unpacked from `apps/extension/` in Chrome/Edge.
2. Visit an `https://` page → service worker logs `Juno capture committed <id>`.
3. `GET /search?q=<title>` with Bearer returns the capture.

CLI equivalent (same payload shape):

```powershell
$token = "<JUNO_API_TOKEN>"
Invoke-RestMethod -Uri http://127.0.0.1:8787/ingest -Method Post `
  -Headers @{ Authorization = "Bearer $token" } `
  -ContentType application/json `
  -Body '{"source_type":"browser","uri":"https://example.com","title":"Example","text":"Example"}'
```

## Deferred to #45+

- Dedupe, excludes, pause backoff, module health, content-script metrics/highlights.

## Links

| Doc | Role |
|-----|------|
| [005-browser-extension-client.md](../adr/005-browser-extension-client.md) | ADR |
| [next-work.md](../next-work.md) | M2 queue + issue numbers |
