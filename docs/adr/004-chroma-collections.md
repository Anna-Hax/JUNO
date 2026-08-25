# ADR-04: Persistent Chroma, one collection per embedding model

## Status

Accepted (v1)

## Date

2026-08-21 (M1 / issue #13)

## Context

Juno stores graph structure in SQLite (`chunks.chroma_id` links a row to a vector). Similarity search needs a **local vector index** that:

- Survives `juno serve` restarts (acceptance for #13)
- Lives under `data/` with the rest of the personal store (gitignored)
- Works with the **stub hash embedder** in CI (no torch / no Chroma default ONNX download)
- Works with MiniLM (or a later model) locally without mixing incompatible vector spaces

Embedding models differ in **dimension and geometry**. Mixing `stub-hash-v1` (64-d) with `all-MiniLM-L6-v2` (384-d) in one collection fails or silently corrupts retrieval. `.env.example` already warns that changing `EMBEDDING_MODEL` requires a reindex.

Chroma I/O is **synchronous**. ADR-01 forbids blocking the shared asyncio loop for long work.

## Options considered

| Option | Summary | Why not (for v1) |
|--------|---------|------------------|
| **A. One collection** | Single index for all embeddings | Dimension / metric mismatch when the model changes |
| **B. Collection per embedding model** | Name derived from `embedder.model_id`; old collections left on disk | Chosen |
| **C. Vectors only in SQLite** | Store blobs next to chunks | No HNSW; retrieval would be a later rewrite |
| **D. Hosted / server Chroma** | Separate process or cloud | Breaks local-first single-process v1 |
| **E. Chroma’s default embedding function** | Let Chroma embed documents | Downloads ONNX in CI; duplicates Juno’s embedder |

## Decision

Use **Chroma `PersistentClient`** on `settings.chroma_path` (`data/chroma/` by default), with **one collection per embedding model**.

Concrete rules (see `juno/graph/vectors.py`):

1. **Persist on disk** — `chromadb.PersistentClient(path=…)` so a new process sees the same vectors.
2. **Collection name** — `collection_name_for_model(embedder.model_id)` → `juno-{sanitized-id}` (Chroma 3–63 char rules). Example: `all-MiniLM-L6-v2` → `juno-all-MiniLM-L6-v2`.
3. **Bring-your-own embeddings** — create collections with `embedding_function=None` and pass vectors from Juno’s `Embedder` on `upsert` / `query`. Do not use Chroma’s default embedder.
4. **Cosine space** — collection metadata sets `hnsw:space=cosine` (embedders L2-normalize).
5. **No telemetry** — `anonymized_telemetry=False` (local-first / privacy).
6. **Event loop** — from `juno serve`, call `upsert_async` / `query_async` (or `asyncio.to_thread` around sync methods). Do not block the loop with raw Chroma I/O.
7. **Model change** — switching `EMBEDDING_MODEL` / backend opens a **new** collection. The old one remains until a later wipe/reindex tool (#23). Retrieval only uses the active model’s collection.

The wrapper is `VectorStore`. Runtime attaches it to `app.state.vectors`. `/status` reports `chroma_collection` and `chroma_count`. Ingest and RAG (#16, #17) write and query through this API; they do not construct a second Chroma client.

## Consequences

### Positive

- Restart-safe vectors next to SQLite under `data/`.
- Safe model switches without corrupting an existing index.
- CI stays stub-only; no extra model download for Chroma.
- One handle in-process (`app.state.vectors`), same pattern as `Database` / embedder.

### Negative / constraints

- Changing models does **not** auto-reindex; search is empty until ingest runs again against the new collection.
- Two collections can coexist on disk (disk use grows if models are swapped often).
- Chroma is another SQLite-backed file tree under `data/chroma/`; backup should include that directory with `juno.db`.
- Callers that pass `query_texts=` without embeddings would fail (no collection embedding function by design).

### Follow-ups

- Ingest pipeline (#16) assigns `chunks.chroma_id` as `c{capture_id}-n{ordinal}` and upserts through the attached `VectorStore`.
- RAG retrieve (#17) should query `VectorStore` then join hits to SQLite captures.
- Export/wipe (#23) should delete or recreate `data/chroma/` as well as the graph DB.
- Optional: record active collection name in SQLite `settings` so `/status` and HITL can explain a model mismatch.
