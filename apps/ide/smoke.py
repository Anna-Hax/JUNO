#!/usr/bin/env python3
"""Spike S3 smoke: read one Cursor session from state.vscdb and POST /ingest.

Stdlib only. Uses apps/ide config + api (ADR-06). Never writes Cursor's DB.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from api import post_ingest  # noqa: E402
from config import load_config  # noqa: E402
from cursor_vscdb import connect_readonly, list_sessions, load_session, to_ingest_payload  # noqa: E402


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
        help="Path to global state.vscdb (default: JUNO_CURSOR_VSCDB or platform path)",
    )
    parser.add_argument("--composer-id", default=None, help="Export this composer id")
    parser.add_argument("--latest", action="store_true", help="Export the newest session")
    parser.add_argument("--limit", type=int, default=8, help="discover: max rows to print")
    parser.add_argument("--post", action="store_true", help="POST the export to /ingest")
    parser.add_argument("--base-url", default=None)
    parser.add_argument("--token", default=None)
    args = parser.parse_args(argv)

    cfg = load_config()
    db_path = args.db or cfg.global_vscdb
    base_url = args.base_url or cfg.api_base_url
    token = args.token if args.token is not None else cfg.api_token
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
        if not (token or "").strip() or token.strip().lower() == "change-me":
            raise SystemExit("Set --token or JUNO_API_TOKEN (not change-me)")
        result = post_ingest(base_url, token, payload)
        if not result.ok:
            raise SystemExit(f"POST {base_url}/ingest failed: {result.status} {result.body}")
        print(json.dumps(result.body, indent=2))
    finally:
        conn.close()


if __name__ == "__main__":
    main()
