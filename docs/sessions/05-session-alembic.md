# Session log: first Alembic revision (#11)

**Date:** 2026-08-22  
**Repo:** [https://github.com/Anna-Hax/JUNO](https://github.com/Anna-Hax/JUNO)  
**Plan:** Personal Knowledge Graph (local-first Python + Telegram)  
**Scope of this session:** M1 issue **#11** — Alembic env + initial schema revision; stop relying on `create_all` for `db-init` / serve.

---

## Summary

Landed revision `0001` matching the current ORM (`captures`, `nodes`, `edges`, `chunks`, `review_items`, `module_health`, `settings`). `juno db-init` and `juno serve` run `Database.migrate()` → `alembic upgrade head`. Databases that were created with M0 `create_all` (no `alembic_version`) are stamped at head so we do not `CREATE TABLE` twice.

Work is on branch `feat/alembic-first-revision` (from `main`; independent of `#13` Chroma). Merged via PR with `Closes #11`.

---

## What changed

### Code

| Path | Role |
|------|------|
| `apps/core/alembic.ini` | Alembic config |
| `apps/core/alembic/env.py` | Sync SQLite URL; batch mode; models as metadata |
| `apps/core/alembic/versions/0001_initial_schema.py` | First revision |
| `apps/core/src/juno/graph/migrations.py` | `upgrade_to_head` / legacy stamp |
| `apps/core/src/juno/graph/db.py` | `migrate()`; `create_all` kept for tests only |
| `apps/core/src/juno/cli.py` | `db-init` calls `migrate()` |
| `apps/core/src/juno/runtime.py` | Lifespan calls `migrate()` |
| `apps/core/src/juno/models/__init__.py` | Alembic naming convention on `Base.metadata` |
| `apps/core/tests/test_migrations.py` | Upgrade, idempotent, stamp, metadata match, CLI |
| `.github/workflows/ci-python.yml` | `alembic upgrade head` on a temp data dir |

Rules encoded in code (see [ADR-03](../adr/003-alembic.md)):

- Migrations use `sqlite:///` (sync) so they can run inside the serve event loop via `asyncio.to_thread`
- Runtime still uses `sqlite+aiosqlite`
- `render_as_batch=True` from day one (SQLite `ALTER` limits)

### Docs

- [003-alembic.md](../adr/003-alembic.md) — transitional `create_all` path retired for CLI/runtime
- Codebase map + next-work + README architecture line

---

## Not in this session

- Later revisions (ingest/HITL columns) — add a new file when models change
- Chroma (#13) — still on `feat/chroma-persistent-client`
- Live Telegram smoke (#4) and Projects board (#9)

---

## How to verify

From `apps/core`:

```powershell
$env:EMBEDDING_BACKEND="stub"
uv run pytest
uv run ruff check src tests
$env:JUNO_DATA_DIR = Join-Path $env:TEMP "juno-alembic-smoke"
New-Item -ItemType Directory -Path $env:JUNO_DATA_DIR | Out-Null
uv run alembic upgrade head
uv run alembic current
uv run juno db-init
```

Expect **11** tests passing (foundation + migrations). `alembic current` prints `0001 (head)`. `db-init` a second time stays at head (`alembic upgrade`).

A DB that already has `captures` but no `alembic_version` (old `create_all`) is stamped, not rebuilt.

---

## Related docs

| File | Contents |
|------|----------|
| [05-session-alembic.md](05-session-alembic.md) | This file |
| [04-session-chroma-client.md](04-session-chroma-client.md) | M1 #13 Chroma session (other branch) |
| [03-next-work.md](03-next-work.md) | #11 done on branch; next M1 work |
| [02-codebase-map.md](02-codebase-map.md) | Alembic + `migrate()` on the module map |
| [../adr/003-alembic.md](../adr/003-alembic.md) | Why Alembic; stamp vs upgrade |
| [../adr/004-chroma-collections.md](../adr/004-chroma-collections.md) | Persistent Chroma; one collection per model |
