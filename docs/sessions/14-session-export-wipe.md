# Session log: export + wipe CLI (#23)

**Date:** 2026-08-26  
**Repo:** [https://github.com/Anna-Hax/JUNO](https://github.com/Anna-Hax/JUNO)  
**Plan:** Personal Knowledge Graph (local-first Python + Telegram)  
**Scope of this session:** M1 issue **#23** — `juno export` + `juno wipe` (full export / delete local data).

---

## Summary

`juno export` dumps all graph tables plus the active Chroma collection (ids, documents, metadatas, embeddings) to JSON under `data/`. `juno wipe --confirm wipe-all-data` deletes the SQLite file and Chroma directory, then runs Alembic `upgrade head` on a fresh database.

Work is on branch `feat/export-wipe-23`. PR / `Closes #23` not opened yet.

---

## What changed

### Code

| Path | Role |
|------|------|
| `apps/core/src/juno/graph/ownership.py` | `build_export_payload`, `write_export_file`, `wipe_local_data` |
| `apps/core/src/juno/graph/vectors.py` | `export_snapshot`, `close` |
| `apps/core/src/juno/cli.py` | `juno export` / `juno wipe` commands |
| `apps/core/tests/test_export.py` | Export payload, confirm gate, wipe paths |

### Docs

- This session file
- README + codebase map + ADR-04
- [`docs/next-work.md`](../next-work.md)

---

## Operational notes

- **Stop `juno serve`** before `juno wipe` on Windows — an open Chroma client can lock files under `data/chroma/`.
- Export uses the configured embedder (falls back to stub if MiniLM is unavailable).

---

## How to verify

From `apps/core`:

```powershell
$env:EMBEDDING_BACKEND="stub"
uv run pytest
uv run ruff check src tests
```

Expect **111** tests passing.

Manual:

```powershell
uv run juno export -o ..\..\data\backup.json
uv run juno wipe --confirm wipe-all-data
uv run juno db-init
```

---

## Related docs

| File | Contents |
|------|----------|
| [14-session-export-wipe.md](14-session-export-wipe.md) | This file |
| [13-session-integration-tests.md](13-session-integration-tests.md) | Merged #22 |
| [../adr/004-chroma-collections.md](../adr/004-chroma-collections.md) | Collection export |
