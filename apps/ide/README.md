# Juno IDE adapter

Loopback **HTTP client** for Cursor chat history and terminal errors ([ADR-06](../../docs/adr/006-ide-adapter-client.md)). Reads `state.vscdb` **read-only** and posts to `juno serve`. Not a second daemon; no Juno SQLite/Chroma handles.

## Layout

| File | Role |
|------|------|
| `config.py` | Paths + token from env / `.env` |
| `cursor_vscdb.py` | Read-only exporter (`composerHeaders` / `bubbleId:`) |
| `api.py` | `GET /status`, `POST /ingest` |
| `smoke.py` | Discover / export one session |
| `sync.py` | Poll watermarked sessions (`--once` or `--watch`) |

## Operator runbook

1. Fill repo-root `.env` (`JUNO_API_TOKEN` not `change-me`). Cursor paths default to the platform `state.vscdb` if unset.
2. Start the core: `cd apps/core` then `uv run juno serve`.
3. Confirm `GET http://127.0.0.1:8787/health` → `{"status":"ok"}`.
4. From the **repo root**, dry-run then commit:

```powershell
python apps/ide/sync.py --once --dry-run
python apps/ide/sync.py --once
```

5. Telegram `/status` should show an `ide` module with `last_success`. `/digest today` groups IDE chats vs IDE errors vs browser vs uploads.
6. Error-like queries use past IDE errors even if the LLM is down. HITL `/review` can confirm `error_match` and `ide_batch` cards.

Leave `--watch` running in a terminal (or a Startup shortcut) if you want continuous poll. Global Telegram `/pause` returns HTTP 423; the adapter backs off that pass.

### Default Cursor paths

| OS | Global `state.vscdb` |
|----|----------------------|
| Windows | `%APPDATA%\Cursor\User\globalStorage\state.vscdb` |
| macOS | `~/Library/Application Support/Cursor/User/globalStorage/state.vscdb` |
| Linux | `~/.config/Cursor/User/globalStorage/state.vscdb` |

Open the DB with SQLite `mode=ro` (copy-to-temp if Cursor has it locked). **Never write** Cursor files.

## Config

Set in repo-root `.env` (same file as `juno serve`):

| Variable | Default |
|----------|---------|
| `JUNO_API_HOST` / `JUNO_API_PORT` | `127.0.0.1` / `8787` |
| `JUNO_API_TOKEN` | required for POST |
| `JUNO_CURSOR_VSCDB` | platform Cursor global `state.vscdb` |
| `JUNO_CURSOR_WORKSPACE_STORAGE` | sibling `workspaceStorage/` |
| `JUNO_CURSOR_WORKSPACE` | optional path substring filter |
| `JUNO_IDE_POLL_SECONDS` | `60` (`--watch`) |
| `JUNO_IDE_STATE` | `{JUNO_DATA_DIR}/ide-adapter.json` watermark |

## Smoke (one session)

```powershell
python apps/ide/smoke.py discover
python apps/ide/smoke.py export --latest --post
```

Then `GET /search?q=<session title>` with Bearer token.

## Poll / watch

```powershell
python apps/ide/sync.py --once --dry-run
python apps/ide/sync.py --once
python apps/ide/sync.py --watch
```

`--watch` polls until Ctrl+C. Re-posting the same `cursor://composer/{id}` or `cursor://error/{id}/{bubble}` updates one capture (no duplicate storms). Terminal command failures (`run_terminal_command_v2` / error-like output) ingest as `raw_json.kind=cursor_error`.

## What lands in the graph

| Kind | `source_type` | URI | `raw_json.kind` |
|------|---------------|-----|-----------------|
| Composer chat | `ide` | `cursor://composer/{id}` | `cursor_chat` |
| Terminal / tool error | `ide` | `cursor://error/{composer}/{bubble}` | `cursor_error` |

Successful ingest updates `module_health.ide` (`GET /status` and Telegram `/status`).

## Troubleshooting

| Symptom | Check |
|---------|--------|
| `discover` returns 0 | Cursor 3.x `composerHeaders` present? Override `JUNO_CURSOR_VSCDB`. Cursor may have migrated keys. |
| Locked DB | Wrapper copies to a temp file; close Cursor only if copy still fails. |
| 401 | Token in `.env` must match `JUNO_API_TOKEN` used by `juno serve`. |
| 423 | Capture is paused (`/resume` in Telegram). |
| Empty assistant bubbles | Tool-call rows are skipped on purpose. |

## CI

```powershell
python scripts/validate-ide.py
cd apps/core
$env:EMBEDDING_BACKEND='stub'
uv run pytest tests/test_ide_scaffold.py tests/test_ide_vscdb.py -q
```
