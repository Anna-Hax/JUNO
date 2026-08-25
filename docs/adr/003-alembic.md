# ADR-03: Alembic from day one

## Status
Accepted (v1)

## Context
The graph schema will churn through M1–M2 (HITL fields, browser metadata, etc.).
`create_all` alone cannot evolve existing user databases safely.

## Decision
- Ship Alembic migrations under `apps/core/alembic/`.
- `juno db-init` and `juno serve` apply `alembic upgrade head` via sync SQLite
  (`sqlite:///`) on a worker thread so the asyncio loop is never nested (ADR-01).
- Databases created with the pre-migration `create_all` path are **stamped** at
  head (tables already match revision `0001`).
- `Base.metadata.create_all` remains for tests and that stamp detection only.
- Schema changes require a new revision (`uv run alembic revision --autogenerate`).

## Consequences
CI runs `alembic upgrade head` against a temp SQLite file, and pytest asserts
the upgraded schema matches ORM metadata. Do not edit models without a revision.
