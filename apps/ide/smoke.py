#!/usr/bin/env python3
"""Spike S3 smoke: read one Cursor session from state.vscdb and POST /ingest.

Stdlib only. Token from JUNO_API_TOKEN or --token. Never writes Cursor's DB.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

# Allow `python apps/ide/smoke.py` from repo root without installing a package.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from cursor_vscdb import (  # noqa: E402
    connect_readonly,
    default_global_vscdb,
    list_sessions,
    load_session,
    to_ingest_payload,
)


def _post_ingest(payload: dict, *, base_url: str, token: str) -> dict:
    url = base_url.rstrip("/") + "/ingest"
    body = json.dumps(payload).encode("utf-8")
    req = Request(
        url,
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else {"status_code": resp.status}
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(f"POST {url} failed: {exc.code} {detail}") from exc
    except URLError as exc:
        raise SystemExit(f"POST {url} failed: {exc.reason}") from exc


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Spike S3: Cursor vscdb → POST /ingest")
    parser.add_argument(
        "command",
        choices=("discover", "export"),
        help="discover sessions, or export one (optionally POST)",
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=None,
        help="Path to global state.vscdb (default: platform Cursor path)",
    )
    parser.add_argument("--composer-id", default=None, help="Export this composer id")
    parser.add_argument("--latest", action="store_true", help="Export the newest session")
    parser.add_argument("--limit", type=int, default=8, help="discover: max rows to print")
    parser.add_argument("--post", action="store_true", help="POST the export to /ingest")
    parser.add_argument("--base-url", default="http://127.0.0.1:8787")
    parser.add_argument("--token", default=os.environ.get("JUNO_API_TOKEN", ""))
    args = parser.parse_args(argv)

    db_path = args.db or default_global_vscdb()
    conn = connect_readonly(db_path)
    try:
        sessions = list_sessions(conn)
        if args.command == "discover":
            print(f"{len(sessions)} session(s) in {db_path}")
            for session in sessions[: max(1, args.limit)]:
                when = session.updated_at.isoformat() if session.updated_at else "?"
                ws = session.workspace_path or session.workspace_id or "-"
                print(f"{session.composer_id}  {when}  {session.name!r}  {ws}")
            return

        composer_id = args.composer_id
        if not composer_id:
            if not args.latest and not sessions:
                raise SystemExit("No composer sessions found")
            if not args.latest and sessions:
                raise SystemExit("Pass --latest or --composer-id")
            if not sessions:
                raise SystemExit("No composer sessions found")
            composer_id = sessions[0].composer_id

        loaded = load_session(conn, composer_id)
        if loaded is None:
            raise SystemExit(f"Session not found: {composer_id}")
        payload = to_ingest_payload(loaded)
        print(json.dumps({k: payload[k] for k in ("source_type", "uri", "title", "visited_at")}, indent=2))
        print(f"bubbles={len(loaded.bubbles)} text_chars={len(payload.get('text') or '')}")
        if not args.post:
            return
        token = (args.token or "").strip()
        if not token or token.lower() == "change-me":
            raise SystemExit("Set --token or JUNO_API_TOKEN (not change-me)")
        result = _post_ingest(payload, base_url=args.base_url, token=token)
        print(json.dumps(result, indent=2))
    finally:
        conn.close()


if __name__ == "__main__":
    main()
