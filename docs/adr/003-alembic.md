# ADR-03: Alembic from day one

## Status

Accepted (v1)

## Date

2026-08-20 (M0 scaffold)  
**Last reviewed:** 2026-09-05 (M5 / #107; schema head is revision `0002`)

## Context

The knowledge-graph schema lives in SQLAlchemy models under `apps/core/src/juno/models/`:

- `captures`, `chunks`, `nodes`, `edges`
- `review_items` (HITL)
- `module_health`, `settings`
- `draft_artifacts` (M5 HITL drafts; [ADR-09](009-draft-artifacts-hitl.md))

That schema will keep evolving past v1.0 (browser metadata in M2, IDE fields in M3, prune / trust dials in M5, and so on). Shipping only `Base.metadata.create_all` at first boot works for empty databases, but it **cannot** safely alter an existing user’s `data/juno.db` when columns or tables change.

Juno is local-first: users keep a long-lived SQLite file. Migrations are not optional polish — they are how we avoid “delete your DB to upgrade.”

We also run under a **shared asyncio loop** ([ADR-01](001-shared-event-loop.md)). Nesting a sync Alembic engine inside an already-running async SQLAlchemy connection is a common source of “loop already running” / deadlocks. Migrations must stay off the serve loop.

## Options considered

| Option | Summary | Why not (for v1) |
|--------|---------|------------------|
| **A. `create_all` only** | Create missing tables at boot | No upgrades for existing files; silent drift from ORM |
| **B. Hand-written SQL scripts** | Ad-hoc `.sql` files | Easy to forget; no revision identity; hard for CI |
| **C. Alembic from day one** | Versioned revisions under `apps/core/alembic/` | **Chosen** |
| **D. Defer Alembic until first breaking change** | Ship `create_all` now, migrate later | Leaves early adopters without a stamp/upgrade story |

## Decision

Use **Alembic** for all schema evolution, starting with the first revision.

Concrete rules:

1. Migrations live under `apps/core/alembic/` with `alembic.ini` in `apps/core/`. Current head: revision **`0002`** (`0002_draft_artifacts.py`) following **`0001`** (`0001_initial_schema.py`).
2. **`juno db-init`** and **`juno serve`** (via `Database.migrate()`) apply `alembic upgrade head`.
3. The upgrade runs on a **sync** SQLite URL (`sqlite:///…`) inside **`asyncio.to_thread`**, so the asyncio loop is never nested (ADR-01). After upgrade, the async engine re-asserts `PRAGMA journal_mode=WAL` ([ADR-02](002-sqlite-write-queue.md)).
4. Databases that were created with the pre-Alembic `create_all` path (tables already match `0001`) are **stamped** at head rather than re-created — see `juno.graph.migrations`.
5. `Base.metadata.create_all` remains for **tests** and for that stamp-detection path only — not as the production upgrade mechanism.
6. **Any** schema change requires a new revision (`uv run alembic revision --autogenerate` from `apps/core`, then review the script). Do not edit models without shipping a migration.

## Consequences

### Positive

- Existing `data/juno.db` files can move forward without a wipe when the schema changes.
- CI runs `alembic upgrade head` against a temp directory before pytest (`.github/workflows/ci-python.yml`).
- Pytest asserts the upgraded schema still matches ORM metadata (`test_migrations.py`).
- `juno wipe` deletes the DB then re-runs migrate so a wiped install is still at head (#23).

### Negative / constraints

- Contributors must remember: model change ⇒ new Alembic revision in the same PR.
- Autogenerate can miss renames / data migrations; always read the generated script.
- **`0002`** adds `draft_artifacts` for HITL drafts ([ADR-09](009-draft-artifacts-hitl.md) / #107). Existing `0001` databases **upgrade**; they are not stamped over `0002`.

### Follow-ups

- M2+ schema additions (browser / IDE capture fields) land as **new revisions**, not edits to `0001`.
- If we ever need data backfills (not just DDL), put them in the revision’s `upgrade()` and keep them idempotent where possible.
- Optional: expose `juno db-current` / `juno db-history` CLI helpers for debugging — not required for v1.0.
