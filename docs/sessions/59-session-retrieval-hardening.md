# Session 59 — retrieval hardening (#128)

**Date:** 2026-09-27  
**Issues:** [#129](https://github.com/Anna-Hax/JUNO/issues/129) [#130](https://github.com/Anna-Hax/JUNO/issues/130) [#131](https://github.com/Anna-Hax/JUNO/issues/131) [#132](https://github.com/Anna-Hax/JUNO/issues/132) [#133](https://github.com/Anna-Hax/JUNO/issues/133) [#134](https://github.com/Anna-Hax/JUNO/issues/134)  
**Epic:** [#128](https://github.com/Anna-Hax/JUNO/issues/128)  
**Branch:** `feat/retrieval-hardening`

## What changed

- Retrieved source bodies are wrapped as untrusted evidence in the answer prompt. Instruction-like phrases are flagged and kept.
- A sourced answer is returned only when the model cites a number that matches this turn's hits. Otherwise the reply stays retrieve-only.
- `retrieve()` fuses vector rank with a keyword rank over stored chunk text. The model does not choose a second search.
- Resurfacing scores relevance, recency, and a light importance weight. Time-ordered questions drop weak hits, then stay oldest-first.
- The polish job queues one template topic summary per day into `/review`. Approve still does not publish it ([ADR-09](../adr/009-draft-artifacts-hitl.md)).
- Each search can append a JSON line under `data/traces/`. `/status` warns on embedder fallback and on a fresh extension heartbeat with no captures in 7 days.

## Verify

```powershell
cd apps/core
$env:EMBEDDING_BACKEND='stub'
uv run pytest -q
uv run ruff check src tests
```
