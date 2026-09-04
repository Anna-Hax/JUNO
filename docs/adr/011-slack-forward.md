# ADR-11: Slack as opt-in link forward, not a workspace bot

## Status

Accepted (M5 / #112)

## Date

2026-09-05

## Context

PRD §6.3 lists Slack as a possible capture surface, but a live workspace listener is a **non-goal** (tokens, always-on bot, channel flood). Operators still want an occasional Slack thread or doc in the graph.

Options:

| Option | Summary | Why not |
|--------|---------|---------|
| **A. Slack Bolt / Events API daemon** | Real-time channel ingest | Second process or extra loop; contradicts [ADR-01](001-shared-event-loop.md) and M5 “not a live listener” |
| **B. Drop-folder only** | Paste exports into `inbox/` | Already works; no Telegram convenience |
| **C. Opt-in Telegram slack.com URLs** | Same ingest path as other links; `JUNO_SLACK_FORWARD` default **off**; HITL like mobile | **Chosen** |

## Decision

1. **No Slack bot, no Events API, no workspace token.** Slack.com hosts in a Telegram message are treated as URLs on the existing ingest pipeline (`source_type=slack`).
2. **Default off.** Without `JUNO_SLACK_FORWARD=true`, the bot explains how to enable and does not fetch.
3. When enabled, the capture still goes through `/review` as a sensitive batch (same HITL as mobile forwards). Trust dial `mobile` stays locked ([ADR-10](010-trust-dials.md)).
4. Prefer Telegram-forward of the text or an `inbox/` drop when the operator does not want network fetch of Slack URLs.

## Consequences

- CI never needs Slack credentials.
- Workspace-wide passive capture stays deferred past M5.
