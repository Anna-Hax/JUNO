# ADR-08: Voice memo transcription privacy

## Status

Accepted (M4 / #91)

## Date

2026-09-04

## Context

PRD open question: transcribe Telegram voice memos **on-device vs API** (cost/privacy). Juno is local-first ([ADR-01](001-shared-event-loop.md)); audio is more sensitive than titles/URLs.

Options:

| Option | Summary | Why not (for v1.3) |
|--------|---------|---------------------|
| **A. Always on-device (faster-whisper)** | No audio leaves the PC | Heavy extra; GPU/CPU; not in the current lockfile |
| **B. Always OpenAI Whisper API** | Simple; good quality | Sends audio off-box; wrong default for local-first |
| **C. Opt-in API, otherwise refuse** | `JUNO_VOICE_BACKEND=auto` uses Whisper **only if** `OPENAI_API_KEY` is set; else a clear bot error | **Chosen** |
| **D. Stub only** | Tests | Not an operator path |

## Decision

1. **Do not persist audio.** Download to memory, transcribe, ingest **text only** (`source_type=telegram`, `raw_json.kind=voice`).
2. **Default `JUNO_VOICE_BACKEND=auto`:** OpenAI-compatible `/audio/transcriptions` when `OPENAI_API_KEY` is present; otherwise `offline` (no upload, bot explains how to enable).
3. `JUNO_VOICE_BACKEND=stub` is tests-only. `off` / `offline` never calls a network STT.
4. Failures reply in Telegram and are visible as `module_health.voice` on serve start.
5. On-device Whisper can replace the OpenAI backend later without changing ingest shape.

## Consequences

- Operators who want voice must accept an API hop **or** wait for a local STT extra.
- Empty `OPENAI_API_KEY` never silently uploads audio.
