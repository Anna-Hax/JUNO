# Session log: MiniLM embedder + LLM health (#14 / #15)

**Date:** 2026-08-26  
**Repo:** [https://github.com/Anna-Hax/JUNO](https://github.com/Anna-Hax/JUNO)  
**Plan:** Personal Knowledge Graph (local-first Python + Telegram)  
**Scope of this session:** M1 issues **#14** (MiniLM path + model id in settings) and **#15** (chat adapters + LLM health in `/status`).

---

## Summary

Confirmed the local MiniLM embedder path without pulling torch in CI (mocked `sentence_transformers` + stub for tests). Serve still falls back to the hash stub if the extra is missing, and `/status` reports the **live** backend so a fallback cannot look like MiniLM.

Chat adapters now include an explicit `offline` provider. `/status` live-probes the attached LLM (`llm_healthy`, `llm_provider`, `llm_model`) instead of a one-shot startup flag. Unhealthy Ollama/OpenAI is retrieve-only for #17.

Work is on branch `feat/embedder-llm-status` (from `main`). PR / `Closes #14` `Closes #15` not opened yet.

---

## What changed

### Code

| Path | Role |
|------|------|
| `apps/core/src/juno/llm/embedder.py` | `backend` on embedders; empty-batch MiniLM; clear missing-extra error |
| `apps/core/src/juno/llm/chat.py` | `offline` factory; Ollama model-in-tags probe; OpenAI `/models` probe |
| `apps/core/src/juno/runtime.py` | Persist `embedding_*` in `settings`; `module_health` row `llm`; warn when unhealthy |
| `apps/core/src/juno/api/__init__.py` | `/status` live LLM probe + actual embedder fields |
| `apps/core/src/juno/config.py` | `llm_provider=offline`; `Settings.llm_model` |
| `apps/core/tests/test_embedder.py` | Batch stub, mocked MiniLM 384-d, persist model id, fallback flag |
| `apps/core/tests/test_chat.py` | Provider switch, health probes, offline complete, `/status` live probe |

Rules encoded in code:

- CI keeps `EMBEDDING_BACKEND=stub` (no torch)
- MiniLM is `uv sync --extra embeddings`; missing extra → ImportError with install hint; `juno serve` catches and uses stub
- `/status.embedding_backend` is the **live** embedder, not the requested env value
- `/status` re-probes chat health (1.5s timeout) so Ollama coming up later is visible without restart
- `LLM_PROVIDER=offline` is a first-class retrieve-only mode

### Docs

- This session file
- README MiniLM extra + `/status` fields
- `.env.example` offline provider + embeddings extra
- Codebase map + [`docs/next-work.md`](../next-work.md)

---

## Not in this session

- PR / merge to `main` (`Closes #14` / `#15`)
- RAG `/search` sourced answers (#17) — next
- Telegram `/status` command (#19)
- Live MiniLM download / Ollama smoke (#4)

---

## How to verify

From `apps/core`:

```powershell
$env:EMBEDDING_BACKEND="stub"
uv run pytest
uv run ruff check src tests
```

Expect **47** tests passing (foundation + ingest + migrations + vectors + embedder + chat).

Manual (after `juno serve`):

```powershell
curl http://127.0.0.1:8787/health
curl -H "Authorization: Bearer <token>" http://127.0.0.1:8787/status
```

`/status` should include `embedding_model`, `embedding_backend`, `embedding_dimensions`, `embedding_fallback`, `llm_healthy`, `llm_provider`, `llm_model`. With Ollama stopped, `llm_healthy` is `false`. With `--extra embeddings` and `EMBEDDING_BACKEND=sentence_transformers`, backend should be `sentence_transformers` and model `all-MiniLM-L6-v2` (first run downloads MiniLM).

---

## Related docs

| File | Contents |
|------|----------|
| [07-session-embedder-llm.md](07-session-embedder-llm.md) | This file |
| [06-session-ingest.md](06-session-ingest.md) | M1 #16 ingest |
| [next-work.md](../next-work.md) | Global next-work tracker |
| [02-codebase-map.md](02-codebase-map.md) | LLM modules on the map |
| [../adr/004-chroma-collections.md](../adr/004-chroma-collections.md) | Collection per embedding model |
