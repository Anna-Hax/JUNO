# Session log: Chroma persistent client (#13)

**Date:** 2026-08-21  
**Repo:** [https://github.com/Anna-Hax/JUNO](https://github.com/Anna-Hax/JUNO)  
**Plan:** Personal Knowledge Graph (local-first Python + Telegram)  
**Scope of this session:** M1 issue **#13** — persistent Chroma wrapper, one collection per embedding model.

---

## Summary

Landed a disk-backed `VectorStore` so embeddings survive process restart. Collections are named from the active embedder model (stub vs MiniLM never share an index). Wired into `juno serve` and `/status`. Ingest and RAG are **not** in this change.

Work is on branch `feat/chroma-persistent-client` (not merged; issue #13 still open until the PR lands).

---

## What changed

### Code

| Path | Role |
|------|------|
| `apps/core/src/juno/graph/vectors.py` | `VectorStore`, `VectorHit`, `collection_name_for_model` |
| `apps/core/src/juno/graph/__init__.py` | Re-exports |
| `apps/core/src/juno/runtime.py` | Builds `VectorStore` and attaches `app.state.vectors` |
| `apps/core/src/juno/api/__init__.py` | `/status` adds `chroma_collection`, `chroma_count`; count via `asyncio.to_thread` |
| `apps/core/tests/conftest.py` | Shared `settings` fixture (`tmp_path`) |
| `apps/core/tests/test_vectors.py` | Persist-across-reopen, per-model isolation, status payload |
| `apps/core/tests/test_foundation.py` | Fixture moved out (behavior unchanged) |

Rules encoded in code (see [ADR-04](../adr/004-chroma-collections.md)):

- `PersistentClient` under `settings.chroma_path` (`data/chroma/`)
- `embedding_function=None` — Juno’s embedder supplies vectors
- `anonymized_telemetry=False`
- Async helpers wrap blocking Chroma I/O (`ADR-01`)

### Docs

- [004-chroma-collections.md](../adr/004-chroma-collections.md)
- Codebase map + next-work updated
- README architecture line points at persistent Chroma

---

## Not in this session

- PR / merge to `main` (`Closes #13`) — not opened yet
- Ingest writing chunks into Chroma (#16)
- RAG `/search` still returns an empty stub (#17)
- First Alembic revision (#11)
- Wipe/export of `data/chroma/` (#23)
- Live Telegram smoke (#4) and Projects board (#9) — still M0 leftovers

---

## How to verify

From `apps/core`:

```powershell
$env:EMBEDDING_BACKEND="stub"
uv run pytest
uv run ruff check src tests
```

Expect **10** tests passing (foundation + vectors).

Manual (after `juno serve`):

```powershell
# unauthenticated
curl http://127.0.0.1:8787/health

# token from .env JUNO_API_TOKEN
curl -H "Authorization: Bearer <token>" http://127.0.0.1:8787/status
```

`/status` should include `chroma_collection` (e.g. `juno-stub-hash-v1` or `juno-all-MiniLM-L6-v2`) and `chroma_count`. After a restart, the same collection name and count remain (until wipe). Vectors live in `data/chroma/` (gitignored).

---

## Related docs

| File | Contents |
|------|----------|
| [04-session-chroma-client.md](04-session-chroma-client.md) | This file |
| [03-next-work.md](03-next-work.md) | Next issue after #13 is **#11** (Alembic) |
| [02-codebase-map.md](02-codebase-map.md) | `graph/vectors.py` on the module map |
| [../adr/004-chroma-collections.md](../adr/004-chroma-collections.md) | Why collection-per-model |
