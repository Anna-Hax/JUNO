# Session log: integration tests (#22)

**Date:** 2026-08-26  
**Repo:** [https://github.com/Anna-Hax/JUNO](https://github.com/Anna-Hax/JUNO)  
**Plan:** Personal Knowledge Graph (local-first Python + Telegram)  
**Scope of this session:** M1 issue **#22** — integration tests ingest → retrieve → review (mocked LLM).

---

## Summary

Added `tests/test_integration.py` with three CI happy paths: pipeline ingest → `GET /search` retrieve → `ReviewQueue` approve; ingest + mocked RAG → skip then approve; `POST /ingest` → search. LLM is mocked via `FakeChat` (same pattern as `test_rag.py`).

Work landed on `main` via [PR #38](https://github.com/Anna-Hax/JUNO/pull/38) (`Closes #22`).

---

## What changed

### Code

| Path | Role |
|------|------|
| `apps/core/tests/test_integration.py` | End-to-end ingest, API search, HITL approve |

### Docs

- This session file
- Codebase map + [`docs/next-work.md`](../next-work.md)

---

## How to verify

From `apps/core`:

```powershell
$env:EMBEDDING_BACKEND="stub"
uv run pytest
uv run ruff check src tests
```

Expect **106** tests passing.

---

## Related docs

| File | Contents |
|------|----------|
| [13-session-integration-tests.md](13-session-integration-tests.md) | This file |
| [12-session-write-queue.md](12-session-write-queue.md) | Merged #12 |
| [next-work.md](../next-work.md) | Global next-work tracker |
