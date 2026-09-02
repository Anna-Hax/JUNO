# Juno IDE adapter (Spike S3)

Loopback **HTTP client** for Cursor chat history. Reads `state.vscdb` **read-only** and posts to `juno serve` `POST /ingest`. It is not a second daemon and does not open Juno's SQLite or Chroma ([ADR-01](../../docs/adr/001-shared-event-loop.md), [ADR-06](../../docs/adr/006-ide-adapter-client.md)).

## Smoke

With `juno serve` running and `JUNO_API_TOKEN` in the environment:

```powershell
python apps/ide/smoke.py discover
python apps/ide/smoke.py export --latest --post
```

Override the DB path or token:

```powershell
python apps/ide/smoke.py export --latest --post --db $env:APPDATA\Cursor\User\globalStorage\state.vscdb --token $env:JUNO_API_TOKEN
```

Confirm: `GET /search?q=<session title>` with Bearer returns the capture (`source_type=ide`).

## Storage we wrap

Cursor (3.x on this machine) stores chats in `%APPDATA%\Cursor\User\globalStorage\state.vscdb`:

| Location | Role |
|----------|------|
| `composerHeaders` | Central session index (id, workspace, timestamps) |
| `cursorDiskKV` `composerData:{id}` | Session envelope + bubble header list |
| `cursorDiskKV` `bubbleId:{id}:{bubbleId}` | Message text |

Empty tool-only bubbles are skipped. Schema is unofficial — if Cursor changes keys, discover will return 0 rows or missing text; see ADR-06 breakage notes.

Watch/poll, config settings, and CI layout land in later M3 issues (#65+).
