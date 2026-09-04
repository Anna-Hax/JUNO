# Session 51 — Flashcards / SRS (#108)

**Date:** 2026-09-05  
**Issue:** [#108](https://github.com/Anna-Hax/JUNO/issues/108) — Flashcards / spaced repetition from highlights  
**Epic:** [#28](https://github.com/Anna-Hax/JUNO/issues/28)  
**Branch:** `feat/flashcards-108`

## What changed

- Scan `raw_json.highlights` → HITL `flashcard` drafts (deduped by fingerprint).
- Approve creates an SRS `flashcards` row (Alembic **0003**); reject does not.
- Telegram `/cards` with Again / Good (SM-2-lite). `/pause` skips generation, not practice of existing due cards.
- Never auto-publish.

## Verify

```powershell
cd apps/core
$env:EMBEDDING_BACKEND='stub'
uv run pytest tests/test_flashcards.py tests/test_migrations.py -q
```

## Deferred

LLM journal/README (#109), skill-gap, trust dial, Slack, prune, polish module health, M5 gate.

## Links

| Doc | Role |
|-----|------|
| [009-draft-artifacts-hitl.md](../adr/009-draft-artifacts-hitl.md) | ADR |
| [next-work.md](../next-work.md) | M5 queue |
