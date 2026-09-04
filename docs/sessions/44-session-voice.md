# Session 44 — Voice memos (#91)

**Date:** 2026-09-04  
**Issue:** [#91](https://github.com/Anna-Hax/JUNO/issues/91)  
**Branch:** `feat/bot-voice-91`

## Decision

Opt-in OpenAI Whisper when `OPENAI_API_KEY` is set; otherwise refuse. Audio is not stored. [ADR-08](../adr/008-voice-transcription.md).

## What changed

- Telegram `filters.VOICE` → transcribe → `POST` ingest path (`raw_json.kind=voice`).
- `module_health.voice` on serve start.

## Verify

```powershell
cd apps/core
$env:EMBEDDING_BACKEND='stub'
uv run pytest tests/test_transcribe.py tests/test_bot.py -q
```
