# Session log: retrieve-only + sourced RAG (#17)

**Date:** 2026-08-26  
**Repo:** [https://github.com/Anna-Hax/JUNO](https://github.com/Anna-Hax/JUNO)  
**Plan:** Personal Knowledge Graph (local-first Python + Telegram)  
**Scope of this session:** M1 issue **#17** — retrieve-only search, sourced RAG answers, citations + confidence.

---

## Summary

`GET /search` queries the attached `VectorStore`, joins hits to SQLite `chunks` / `captures`, and always returns citations plus a confidence score (cosine similarity). When a chat provider is healthy it generates a sourced answer (`mode=rag`); if the LLM is down, errors, or `mode=retrieve` is requested, the same hits are returned without an answer (`mode=retrieve`).

Work is on branch `feat/rag-retrieve` (from `main`). PR / `Closes #17` not opened yet.

---

## What changed

### Code

| Path | Role |
|------|------|
| `apps/core/src/juno/rag/engine.py` | Retrieve + optional generate; join Chroma ids to captures |
| `apps/core/src/juno/rag/__init__.py` | Package exports |
| `apps/core/src/juno/api/__init__.py` | `/search?q=&k=&mode=` wired; `create_app(..., chat=)` |
| `apps/core/tests/test_rag.py` | Token, join/citations, empty index, RAG mock, unhealthy/error fallback |

Rules encoded in code:

- Chroma I/O stays on `query_async` (ADR-01 / ADR-04)
- Citations are required on every response (`citations` mirrors hits, or the `[n]` subset after generate)
- Confidence is `max(score)` over the cited hits; score is `1 - cosine distance`
- LLM generate is skipped when `chat` is missing/unhealthy, `complete` raises, or the answer is empty
- Health probe uses `healthy(timeout=1.5)` (same as `/status` after PR #32)
- Stub embedder tests query the **same** ingested string (hash vectors are not semantic)
- `LLM_PROVIDER=offline` / `OfflineProvider` stays retrieve-only

### Docs

- This session file
- Codebase map + [`docs/next-work.md`](../next-work.md)
- ADR-04 follow-up for #17 marked done
- README `/search` line

---

## Not in this session

- PR / merge to `main` (`Closes #17`)
- Telegram text query using RAG (#18)
- Live MiniLM / Ollama smoke (#4)

Merged [PR #32](https://github.com/Anna-Hax/JUNO/pull/32) into this branch; `/status` live probe and `/search` both remain.

---

## How to verify

From `apps/core`:

```powershell
$env:EMBEDDING_BACKEND="stub"
uv run pytest
uv run ruff check src tests
```

Expect **56** tests passing (foundation + ingest + migrations + vectors + embedder + chat + 9 RAG).

Manual (after ingesting something, `juno serve`):

```powershell
curl -H "Authorization: Bearer <token>" "http://127.0.0.1:8787/search?q=your+query&mode=retrieve"
```

Response should include `results`, `citations`, and `confidence`. With Ollama healthy and `mode=auto`, `mode` becomes `rag` and `answer` is set.

---

## Related docs

| File | Contents |
|------|----------|
| [08-session-rag.md](08-session-rag.md) | This file |
| [06-session-ingest.md](06-session-ingest.md) | M1 #16 ingest |
| [07-session-embedder-llm.md](07-session-embedder-llm.md) | M1 #14 / #15 MiniLM + LLM health (PR #32, now on this branch) |
| [next-work.md](../next-work.md) | Global next-work tracker |
| [../adr/004-chroma-collections.md](../adr/004-chroma-collections.md) | Query `VectorStore`, then join SQLite |
