# Juno IDE adapter

Loopback **HTTP client** for Cursor chat history ([ADR-06](../../docs/adr/006-ide-adapter-client.md)). Reads `state.vscdb` **read-only** and posts to `juno serve`. Not a second daemon; no Juno SQLite/Chroma handles.

## Layout

| File | Role |
|------|------|
| `config.py` | Paths + token from env / `.env` |
| `cursor_vscdb.py` | Read-only exporter (`composerHeaders` / `bubbleId:`) |
| `api.py` | `GET /status`, `POST /ingest` |
| `smoke.py` | Discover / export one session |
| `sync.py` | Poll watermarked sessions (`--once` or `--watch`) |

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

## Smoke

```powershell
python apps/ide/smoke.py discover
python apps/ide/smoke.py export --latest --post
```

## Poll / watch

```powershell
python apps/ide/sync.py --once --dry-run
python apps/ide/sync.py --once
python apps/ide/sync.py --watch
```

`--watch` polls until Ctrl+C. Global `/pause` returns 423; the adapter backs off that pass. Re-posting the same `cursor://composer/{id}` or `cursor://error/{id}/{bubble}` updates one capture (no duplicate storms). Terminal command failures (`run_terminal_command_v2` / error-like output) ingest as `raw_json.kind=cursor_error`.

## CI

```powershell
python scripts/validate-ide.py
```
