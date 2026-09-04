# ADR-10: Per-category trust dials

## Status

Accepted (M5 / #111)

## Date

2026-09-05

## Context

PRD §8 P2: as the agent earns confidence in a category, that category's gate can loosen while tighter categories (mobile, drafts) stay gated. This must be an **explicit per-category setting**, not a global switch.

## Decision

1. Store dials in `settings` (`trust.{category}.successes` / `.auto` / `.threshold`). No extra table.
2. Categories: `merge`, `browser`, `ide_error`, `mobile`, `drafts`.
3. **`mobile` and `drafts` are locked** — `/trust mobile on` is rejected; `should_auto_commit` is always false.
4. Five successful Approve taps on `merge` or `ide_error` turns auto-commit **on** for that category. High-confidence (`>= 0.8`) merges then commit without a pending `/review` card (audit row still stored as decided).
5. Operator can `/trust merge|browser|ide_error on|off`. `/status` lists current dials.

## Consequences

- Early graphs stay HITL-heavy; a month of good merge reviews can loosen only merges.
- Draft auto-publish remains forbidden ([ADR-09](009-draft-artifacts-hitl.md)).
