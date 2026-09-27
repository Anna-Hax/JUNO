# ADR-13: Retrieved text is evidence, and a sourced answer must cite it

## Status

Accepted (post-v2.0)

## Date

2026-09-27

## Context

Browser pages, inbox files, and notes are stored and later placed next to the system rules when Juno answers. A page can contain text that looks like an instruction. Separately, an answer with no `[n]` marker was treated as if every retrieved hit had been cited, and the reported confidence was the best cosine.

Search is still chosen in code. The model writes a paragraph from the hits it is given. It does not pick tools or run a second search.

## Decision

1. Each source body in the answer prompt is wrapped in `<UNTRUSTED_CONTENT>` markers. The system line says that text is data, not a command. Instruction-like phrases are flagged and left in place.
2. If the model does not cite an in-range `[n]`, the turn stays retrieve-only. Citations on a sourced answer are only the hits it named. Confidence for that mode is the best score among those cited hits.
3. Keyword rank over chunk text is fused with the vector ranking inside `retrieve()`. A failure of the keyword pass leaves the vector order. Archived captures stay out of the keyword corpus.
4. Resurfacing uses a salience score (relevance, a recency factor that does not zero out older notes, highlights up, very short text down). The push versus `/review` split stays.
5. A nightly-style consolidation is a template topic summary on the existing polish job, queued as a draft. Approve does not publish it ([ADR-09](009-draft-artifacts-hitl.md)).
6. Search traces are local JSON lines under the data directory. `/status` warns when the embedder fell back to the stub, and when the extension heartbeat is fresh but no capture landed in the last 7 days. Choosing the stub embedder on purpose is not a warning.

## Consequences

- Operators see snippets instead of a paragraph when the model will not cite.
- Exact tokens can outrank a merely nearby vector hit.
- Topic summaries show up in `/review` at most once per day, and only when there are at least two recent captures.
