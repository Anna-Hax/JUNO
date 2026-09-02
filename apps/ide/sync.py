#!/usr/bin/env python3
"""Poll Cursor state.vscdb and POST new/updated chats + errors to loopback /ingest.

HTTP client only (ADR-06). Watermark is a local JSON file, not Juno SQLite/Chroma.
Core upserts by URI so re-posts update one capture.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from api import post_ingest  # noqa: E402
from config import IdeConfig, load_config  # noqa: E402
from cursor_vscdb import (  # noqa: E402
    CursorSession,
    connect_readonly,
    extract_errors,
    list_sessions,
    load_session,
    to_error_ingest_payload,
    to_ingest_payload,
)


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def load_watermark(path: Path) -> datetime | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    return _parse_iso(str(data.get("watermark") or ""))


def save_watermark(path: Path, when: datetime) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"watermark": when.astimezone(UTC).isoformat(), "module": "ide"}, indent=2)
        + "\n",
        encoding="utf-8",
    )


def _matches_workspace(session: CursorSession, filt: str | None) -> bool:
    if not filt:
        return True
    needle = filt.casefold()
    hay = " ".join(
        part for part in (session.workspace_path, session.workspace_id, session.name) if part
    )
    return needle in hay.casefold()


def due_sessions(
    sessions: list[CursorSession],
    *,
    watermark: datetime | None,
    limit: int,
    workspace_filter: str | None,
) -> list[CursorSession]:
    newer: list[CursorSession] = []
    for session in sessions:
        if not _matches_workspace(session, workspace_filter):
            continue
        if watermark is not None and session.updated_at is not None:
            if session.updated_at <= watermark:
                continue
        newer.append(session)
    batch = newer[: max(1, limit)]
    return list(reversed(batch))


def sync_once(cfg: IdeConfig, *, limit: int, dry_run: bool) -> tuple[int, int]:
    """Return (posted, paused_or_failed)."""
    conn = connect_readonly(cfg.global_vscdb)
    try:
        sessions = list_sessions(conn)
        watermark = load_watermark(cfg.state_path)
        due = due_sessions(
            sessions,
            watermark=watermark,
            limit=limit,
            workspace_filter=cfg.workspace_filter,
        )
        posted = 0
        blocked = 0
        latest = watermark
        for meta in due:
            loaded = load_session(conn, meta.composer_id)
            if loaded is None:
                continue
            errors = extract_errors(
                conn, loaded.composer_id, workspace_path=loaded.workspace_path
            )
            if not loaded.bubbles and not errors:
                continue
            if loaded.bubbles:
                payload = to_ingest_payload(loaded)
                if dry_run:
                    print(f"dry-run {payload['uri']} {payload['title']!r}")
                    posted += 1
                else:
                    if not cfg.token_is_usable():
                        raise SystemExit("Set JUNO_API_TOKEN (not change-me)")
                    result = post_ingest(cfg.api_base_url, cfg.api_token, payload)
                    if result.paused:
                        print("capture paused (423) — backing off")
                        blocked += 1
                        break
                    if not result.ok:
                        print(f"ingest failed {result.status}: {result.body}")
                        blocked += 1
                    else:
                        print(f"committed {result.body.get('capture_id')} {payload['uri']}")
                        posted += 1
            stop = False
            for err in errors:
                err_payload = to_error_ingest_payload(err)
                if dry_run:
                    print(f"dry-run {err_payload['uri']} {err_payload['title']!r}")
                    posted += 1
                    continue
                if not cfg.token_is_usable():
                    raise SystemExit("Set JUNO_API_TOKEN (not change-me)")
                err_result = post_ingest(cfg.api_base_url, cfg.api_token, err_payload)
                if err_result.paused:
                    print("capture paused (423) — backing off")
                    blocked += 1
                    stop = True
                    break
                if not err_result.ok:
                    print(f"ingest failed {err_result.status}: {err_result.body}")
                    blocked += 1
                    continue
                print(f"committed {err_result.body.get('capture_id')} {err_payload['uri']}")
                posted += 1
            if stop:
                break
            if loaded.updated_at and (latest is None or loaded.updated_at > latest):
                latest = loaded.updated_at
        if not dry_run and latest is not None and posted:
            save_watermark(cfg.state_path, latest)
        return posted, blocked
    finally:
        conn.close()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Poll Cursor chats → POST /ingest")
    parser.add_argument("--once", action="store_true", help="Single pass (default)")
    parser.add_argument("--watch", action="store_true", help="Poll until interrupted")
    parser.add_argument("--limit", type=int, default=8, help="Max sessions per pass")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    cfg = load_config()
    watch = args.watch
    while True:
        posted, blocked = sync_once(cfg, limit=args.limit, dry_run=args.dry_run)
        print(f"sync posted={posted} blocked={blocked} db={cfg.global_vscdb}")
        if not watch:
            return
        time.sleep(cfg.poll_seconds)


if __name__ == "__main__":
    main()
