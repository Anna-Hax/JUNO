# Session 24 — Domain excludes + pause (#49)

**Date:** 2026-08-29  
**Issue:** [#49](https://github.com/Anna-Hax/JUNO/issues/49)  
**Branch:** `feat/domain-excludes-pause-49`

## What changed

- `lib/excludes.js` + options textarea for excluded domains (defaults: chase.com, paypal.com, bankofamerica.com).
- Background skips excluded hosts; backs off on API **423** (global `/pause`); polls `/status` every 60s.

## Verify

- Visit excluded domain → no ingest log.
- Telegram `/pause` → extension stops ingesting until `/resume`.
