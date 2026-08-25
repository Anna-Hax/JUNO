# Session log: v1.0 release gate (#24)

**Date:** 2026-08-26  
**Repo:** [https://github.com/Anna-Hax/JUNO](https://github.com/Anna-Hax/JUNO)  
**Scope:** M1 issue **#24** — v1.0 release gate checklist (all M1 P0 closed).

---

## Summary

Added [`docs/v1.0-release-gate.md`](../v1.0-release-gate.md) documenting every M1 P0/P1 issue and its merge PR. Bumped package version to **1.0.0**. Updated README + [`docs/next-work.md`](../next-work.md) to mark M1 foundation complete and point at M2 epic **#25**.

Work is on branch `chore/v1-release-gate-24`. PR / `Closes #24` not opened yet.

---

## What changed

| Path | Role |
|------|------|
| `docs/v1.0-release-gate.md` | Checklist + CI gate + manual smoke pointers |
| `apps/core/pyproject.toml` | version `1.0.0` |
| `apps/core/src/juno/__init__.py` | `__version__ = "1.0.0"` |
| `README.md` | Status line |
| `docs/next-work.md` | M1 complete; next = M2 |

---

## How to verify

```powershell
cd apps/core
$env:EMBEDDING_BACKEND="stub"
uv run pytest -q
uv run juno version   # expect 1.0.0
```

Review [`docs/v1.0-release-gate.md`](../v1.0-release-gate.md) — all M1 P0 rows should show ✅.

---

## Related

| File | Contents |
|------|----------|
| [15-session-v1-release-gate.md](15-session-v1-release-gate.md) | This file |
| [v1.0-release-gate.md](../v1.0-release-gate.md) | The gate checklist |
