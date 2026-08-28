# ADR-05: Browser extension as loopback HTTP client

## Status

Accepted (M2 / Spike S2)

## Date

2026-08-29

## Context

M2 needs passive browser reading capture (URL, title, later metrics/highlights). Options:

1. **Custom MV3 extension** posting to `POST /ingest` on the loopback API.
2. **Chrome history/bookmarks APIs** only — no extension, or a thinner add-on.

Juno already enforces:

- One serve process ([ADR-01](001-shared-event-loop.md))
- No second Chroma/SQLite client in the extension ([ADR-04](004-chroma-collections.md))
- Loopback + Bearer token ([#21](https://github.com/Anna-Hax/JUNO/issues/21))

## Decision

Ship a **custom MV3 extension** (`apps/extension/`) that is an **HTTP client only**:

- `host_permissions` for `http://127.0.0.1:8787/*` (configurable base URL in options).
- Service worker listens to `tabs.onUpdated` (complete) and `fetch`es `POST /ingest` with `Authorization: Bearer <JUNO_API_TOKEN>`.
- Token and base URL in `chrome.storage.sync` (options UI).
- `source_type=browser` payloads: `uri`, `title`, `text` (title fallback until full page extract).

Do **not** use History API as the primary capture path — it lacks timely title pairing, cannot attach highlights, and does not fit the same auth/pause/excludes model.

## Consequences

### Positive

- Same ingest pipeline, write queue, and vectors as Telegram/inbox.
- Extension stays a thin client; schema changes remain server-side (Alembic).
- Easy to extend with content scripts for scroll/highlights later.

### Negative

- User must load unpacked extension (store packaging is out of M2 scope).
- Service worker must handle `juno serve` being down (log + retry later in module health #50).
- Per-tab capture on `complete` can duplicate on SPA navigations — dedupe/excludes land in #49.

## Spike S2 proof

Issue [#44](https://github.com/Anna-Hax/JUNO/issues/44): MV3 service worker + options + successful `POST /ingest` against local `juno serve` (see [session 19](../sessions/19-session-spike-s2.md)).
