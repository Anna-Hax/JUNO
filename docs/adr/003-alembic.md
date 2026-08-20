# ADR-03: Alembic from day one

## Status
Accepted (v1)

## Context
The graph schema will churn through M1–M2 (HITL fields, browser metadata, etc.).
`create_all` alone cannot evolve existing user databases safely.

## Decision
- Ship Alembic migrations under `apps/core/alembic/`.
- `juno db-init` may still call `create_all` for fresh installs; upgrades use
  `alembic upgrade head`.
- v0.1 scaffold uses `create_all` until the first migration revision is added.

## Consequences
Schema changes require a migration file. CI should run migrations against a
temp DB once revisions exist.
