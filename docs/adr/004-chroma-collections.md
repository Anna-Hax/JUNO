# ADR-04: Persistent Chroma, one collection per embedding model

## Status

Accepted (v1)

## Date

2026-08-21 (M1 / issue #13)  
**Last reviewed:** 2026-08-26 (after M1 / v1.0 — ingest, RAG, export/wipe landed)

## Context

Juno stores graph structure in SQLite. Chunks of captured text need a **local vector index** for similarity search so Telegram / `GET /search` can find “that thing I read” without scanning every row.

Requirements for v1:

- Survive `juno serve` restarts (acceptance for [#13](https://github.com/Anna-Hax/JUNO/issues/13)).
- Live under `data/` with the rest of the personal store (gitignored).
- Work with the **stub hash embedder** in CI (no torch / no Chroma default ONNX download).
- Work with MiniLM (or a later model) locally without mixing incompatible vector spaces.
- Respect the shared asyncio loop ([ADR-01](001-shared-event-loop.md)) — Chroma’s client API is synchronous.

Embedding models differ in **dimension and geometry**. Mixing `stub-hash-v1` (64-d) with `all-MiniLM-L6-v2` (384-d) in one collection fails or silently corrupts retrieval. `.env.example` warns that changing `EMBEDDING_MODEL` / backend requires a reindex.

SQLite already holds the canonical text and `chunks.chroma_id` (the join key). Chroma holds the vectors for nearest-neighbor search only.

## Options considered

| Option | Summary | Why not (for v1) |
|--------|---------|------------------|
| **A. One collection for all models** | Single index | Dimension / metric mismatch when the model changes |
| **B. Collection per embedding model** | Name derived from `embedder.model_id`; old collections left on disk | **Chosen** |
| **C. Vectors only in SQLite** | Store blobs next to chunks | No HNSW; retrieval would be a later rewrite |
| **D. Hosted / server Chroma** | Separate process or cloud | Breaks local-first single-process v1 |
| **E. Chroma’s default embedding function** | Let Chroma embed documents | Downloads ONNX in CI; duplicates Juno’s embedder |

## Decision

Use **Chroma `PersistentClient`** on `settings.chroma_path` (`data/chroma/` by default), with **one collection per embedding model**.

Concrete rules (implemented in `apps/core/src/juno/graph/vectors.py` as `VectorStore`):

1. **Persist on disk** — `chromadb.PersistentClient(path=…)` so a new process sees the same vectors.
2. **Collection name** — `collection_name_for_model(embedder.model_id)` → `juno-{sanitized-id}` (Chroma 3–63 character rules). Example: `all-MiniLM-L6-v2` → `juno-all-MiniLM-L6-v2`.
3. **Bring-your-own embeddings** — create collections with `embedding_function=None` and pass vectors from Juno’s `Embedder` on `upsert` / `query`. Do **not** use Chroma’s default embedder.
4. **Cosine space** — collection metadata sets `hnsw:space=cosine` (embedders L2-normalize).
5. **No telemetry** — `anonymized_telemetry=False` (local-first / privacy).
6. **Event loop** — from `juno serve`, call `upsert_async` / `query_async` (wrappers around `asyncio.to_thread`). Do not block the loop with raw Chroma I/O.
7. **Model change** — switching `EMBEDDING_MODEL` / backend opens a **new** collection. The old one remains on disk until wiped. Retrieval only uses the **active** model’s collection.
8. **Chunk IDs** — ingest assigns `chunks.chroma_id` as `c{capture_id}-n{ordinal}` and upserts those IDs into Chroma so RAG can join hits back to SQLite captures.

Runtime attaches a single `VectorStore` to `app.state.vectors`. `/status` and Telegram `/status` report `chroma_collection` and `chroma_count`. Ingest, RAG, and export all use that handle; they do not construct a second Chroma client.

### Export and wipe (#23)

- **`juno export`** dumps all graph tables plus the **active** collection snapshot (ids, documents, metadatas, embeddings) via `VectorStore.export_snapshot()` / `juno.graph.ownership`.
- **`juno wipe --confirm wipe-all-data`** deletes `data/juno.db` and the entire `data/chroma/` tree, then re-runs Alembic migrations on a fresh database ([ADR-03](003-alembic.md)).
- **Stop `juno serve` before wipe on Windows** — an open `PersistentClient` can lock files under `data/chroma/` (`PermissionError`). `VectorStore.close()` exists for tests / CLI; the operator still must not wipe while serve is running.

## Consequences

### Positive

- Restart-safe vectors next to SQLite under `data/`.
- Safe model switches without corrupting an existing index.
- CI stays stub-only; no extra model download for Chroma.
- One in-process handle (`app.state.vectors`), same pattern as `Database` / embedder.
- Full local backup via `juno export`; full delete via `juno wipe` (data ownership / PRD §9).

### Negative / constraints

- Changing models does **not** auto-reindex; search is empty on the new collection until content is ingested again.
- Two (or more) collections can coexist on disk — disk use grows if models are swapped often; wipe is the blunt cleanup.
- Chroma is another SQLite-backed file tree under `data/chroma/`; any manual backup should include that directory with `juno.db` (or use `juno export`).
- Callers that pass `query_texts=` without embeddings would fail (no collection embedding function by design).
- Windows file locks make in-process wipe while a client is open unreliable — document and enforce “serve stopped”.

### What landed (M1)

- Persistent client + per-model collections ([#13](https://github.com/Anna-Hax/JUNO/issues/13)).
- Ingest upserts through the attached `VectorStore` with `c{capture_id}-n{ordinal}` IDs ([#16](https://github.com/Anna-Hax/JUNO/issues/16)).
- RAG retrieve queries Chroma then joins to SQLite (`juno.rag.engine`, [#17](https://github.com/Anna-Hax/JUNO/issues/17)).
- Embedder model / backend / dimensions persisted into SQLite `settings` on serve for later reindex awareness ([#14](https://github.com/Anna-Hax/JUNO/issues/14)).
- Export / wipe CLI ([#23](https://github.com/Anna-Hax/JUNO/issues/23)).

### Follow-ups (post–v1.0)

- Optional **reindex** command: rebuild the active collection from SQLite `chunks` after an embedding model change (wipe deletes everything; reindex would migrate).
- Optionally persist the **collection name** itself in SQLite `settings` (today we persist `embedding_model` / `embedding_backend` / `embedding_dimensions`, and `/status` reads the live `VectorStore.collection_name`).
- M2+ capture modules must reuse the same `VectorStore` instance from runtime — do not open a second PersistentClient in the browser extension path (extension talks HTTP to the loopback API instead).
