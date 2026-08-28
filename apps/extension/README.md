# Juno Capture (browser extension)

MV3 **loopback client** for [Juno](../../README.md). Sends page visits to local `juno serve` via `POST /ingest` — no direct SQLite/Chroma access ([ADR-05](../../docs/adr/005-browser-extension-client.md)).

## Load unpacked (Chrome / Edge)

1. Start the core: `cd apps/core && uv run juno serve`
2. Open `chrome://extensions` → **Developer mode** → **Load unpacked**
3. Select this folder: `apps/extension/`
4. Click the Juno toolbar icon → **Options…** (or right-click → Options)
5. Set **API base URL** (`http://127.0.0.1:8787`) and **API token** (same as `JUNO_API_TOKEN` in repo-root `.env`)
6. Browse an `https://` page — check service worker console for `Juno capture committed`

## Layout

| Path | Role |
|------|------|
| `manifest.json` | MV3 permissions (`storage`, `tabs`, loopback host) |
| `background.js` | Service worker — tab capture orchestration |
| `lib/config.js` | `chrome.storage.sync` settings |
| `lib/api.js` | Bearer-authenticated fetch to `/status` and `/ingest` |
| `options.html` | Full settings page |
| `popup.html` | Quick connection status |

## Privacy

- Only talks to `127.0.0.1` (configurable base URL).
- Token stays in extension storage on your machine.
- Respects global capture pause when API returns 423 (see core `/pause`).
