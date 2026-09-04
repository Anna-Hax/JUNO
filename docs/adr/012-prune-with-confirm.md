# ADR-12: Prune is HITL archive, never silent delete

## Status

Accepted (M5 / #113)

## Date

2026-09-05

## Context

PRD §8 P0 / open question on retention: low-value captures (old unused notes, failed ingest) should be cleanable without a full `juno wipe` ([#23](https://github.com/Anna-Hax/JUNO/issues/23)). Silent or scheduled delete would fight the HITL layer ([ADR-09](009-draft-artifacts-hitl.md), [ADR-10](010-trust-dials.md)).

Options:

| Option | Summary | Why not |
|--------|---------|---------|
| **A. Cron auto-delete** | Age out after N days | Silent destructive write; violates “never silent delete” |
| **B. `juno wipe` only** | Nuclear option already exists | Too coarse; operators lose the whole graph |
| **C. HITL prune → archive** | List candidates; queue `kind=prune`; Approve sets `status=archived` and drops Chroma ids | **Chosen** |

## Decision

1. **Propose ≠ destroy.** `/prune` and `juno prune` only list or enqueue. Archive happens solely on `/review` Approve.
2. **CLI confirm queues, it does not delete.** `juno prune --confirm prune-selected` is distinct from `wipe-all-data`. Wrong phrase refuses the queue.
3. **Archive, don’t wipe.** SQLite rows stay (`status=archived`) so export can still see them; vectors for those chunks are deleted ([ADR-04](004-chroma-collections.md)). Retrieval skips archived captures.
4. **Trust dial `prune` is locked** — no auto-commit ([ADR-10](010-trust-dials.md)).
5. Optional `juno prune --export PATH --confirm prune-selected` writes a full graph export first.
6. Writes go through `Database.write()` ([ADR-02](002-sqlite-write-queue.md)). No extra Alembic table.

## Consequences

- Failed ingest older than 7 days and unused committed captures older than `JUNO_PRUNE_MIN_AGE_DAYS` (default 90) are candidates.
- Highlighted or graph-linked captures are not unused.
- Full disk wipe remains `juno wipe --confirm wipe-all-data`.
