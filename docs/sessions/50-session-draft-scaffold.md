# Session 50 — Draft artifacts scaffold (#107)

**Date:** 2026-09-05  
**Issue:** [#107](https://github.com/Anna-Hax/JUNO/issues/107) — Draft artifacts scaffold: draft kinds + never auto-publish  
**Epic:** [#28](https://github.com/Anna-Hax/JUNO/issues/28)  
**Branch:** `feat/draft-scaffold-107`

## What changed

- Kinds `journal` / `flashcard` / `doc` (`juno.drafts.kinds`); unknown kinds raise.
- `draft_artifacts` table via Alembic **0002**; approve confirms, reject discards, `published` stays `false`.
- Template enqueue helpers for flashcard + doc (no LLM). Journal smoke path unchanged.
- ADR-09 scaffold note; ADR-03 head is `0002`.

## Verify

```powershell
cd apps/core
$env:EMBEDDING_BACKEND='stub'
uv run pytest tests/test_drafts.py tests/test_migrations.py -q
```

## Deferred

Flashcard SRS (#108), LLM journal/README (#109), skill-gap, trust dial, Slack, prune, polish health, M5 gate.

## Links

| Doc | Role |
|-----|------|
| [009-draft-artifacts-hitl.md](../adr/009-draft-artifacts-hitl.md) | ADR |
| [003-alembic.md](../adr/003-alembic.md) | Schema head 0002 |
| [next-work.md](../next-work.md) | M5 queue |
