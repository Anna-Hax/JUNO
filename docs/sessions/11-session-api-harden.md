# Session log: harden local API (#21)

**Date:** 2026-08-26  
**Repo:** [https://github.com/Anna-Hax/JUNO](https://github.com/Anna-Hax/JUNO)  
**Plan:** Personal Knowledge Graph (local-first Python + Telegram)  
**Scope of this session:** M1 issue **#21** — loopback FastAPI `/health` `/status` `/ingest` `/search` + token auth (bad token 401).

---

## Summary

Routes were already stubbed (ingest persists; search retrieves). This pass fails closed: a missing, wrong, or example `change-me` token is **401**; `juno serve` refuses to bind a non-loopback host or start with the example token; `/docs` is off; `/ingest` no longer returns a fake `{accepted: true}` when the pipeline is missing (503 instead).

Work is on branch `feat/api-harden-21`. PR / `Closes #21` not opened yet.

---

## What changed

### Code

| Path | Role |
|------|------|
| `apps/core/src/juno/config.py` | Token / loopback helpers; `validate_serve_settings` |
| `apps/core/src/juno/api/__init__.py` | Timing-safe Bearer check; loopback middleware; no OpenAPI; ingest 503 |
| `apps/core/src/juno/runtime.py` | Serve calls `validate_serve_settings` before listen |
| `apps/core/tests/test_api.py` | 401 / 403 / default-token / 503 coverage |
| `apps/core/tests/test_foundation.py` | Ingest smoke expects 503 without a pipeline |

Rules encoded in code:

- `/health` stays unauthenticated (liveness); `/status` `/ingest` `/search` require `Authorization: Bearer …`
- Empty token and `change-me` never authorize, even if the header matches
- Client hosts other than loopback (`127.0.0.1` / `::1` / `localhost` / IPv4-mapped) get **403**
- `JUNO_API_HOST=0.0.0.0` (or any non-loopback) is rejected at serve start
- OpenAPI `/docs` `/redoc` `/openapi.json` are disabled

### Docs

- This session file
- Codebase map + [`docs/next-work.md`](../next-work.md) + README / `.env.example`

---

## Not in this session

- PR / merge to `main` (`Closes #21`)
- Concurrent ingest lock test (#12)
- Integration tests (#22) and export/wipe (#23)

---

## How to verify

From `apps/core`:

```powershell
$env:EMBEDDING_BACKEND="stub"
uv run pytest
uv run ruff check src tests
```

Expect **100** tests passing.

Manual (after setting a real `JUNO_API_TOKEN` in `.env`):

```powershell
# missing token
curl http://127.0.0.1:8787/status
# expect 401

curl -H "Authorization: Bearer <token>" http://127.0.0.1:8787/status
# expect 200
```

`juno serve` with `JUNO_API_TOKEN=change-me` or `JUNO_API_HOST=0.0.0.0` should refuse to start.

---

## Related docs

| File | Contents |
|------|----------|
| [11-session-api-harden.md](11-session-api-harden.md) | This file |
| [10-session-hitl-review.md](10-session-hitl-review.md) | Merged #20 HITL |
| [next-work.md](../next-work.md) | Global next-work tracker |
| [02-codebase-map.md](02-codebase-map.md) | API constraints |
