"""Read-only Cursor chat exporter from local ``state.vscdb``.

Wraps the community-documented Cursor storage schema (same keys as
cursor-chat-export / cursor-session / cursaves):

- ``composerHeaders`` table or ``composer.composerHeaders`` in ItemTable
- ``cursorDiskKV`` keys ``composerData:{id}`` and ``bubbleId:{id}:{bubbleId}``

Never writes to Cursor's DB. Open with SQLite URI ``mode=ro``.
"""

from __future__ import annotations

import json
import os
import sqlite3
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROLE_BY_TYPE = {1: "user", 2: "assistant"}


@dataclass(frozen=True)
class Bubble:
    bubble_id: str
    role: str
    text: str
    created_at: str | None = None


@dataclass(frozen=True)
class CursorSession:
    composer_id: str
    name: str
    created_at: datetime | None
    updated_at: datetime | None
    workspace_id: str | None = None
    workspace_path: str | None = None
    mode: str | None = None
    bubbles: tuple[Bubble, ...] = field(default_factory=tuple)

    @property
    def uri(self) -> str:
        return f"cursor://composer/{self.composer_id}"


def default_global_vscdb() -> Path:
    """Platform default for Cursor's global ``state.vscdb``."""
    if sys.platform == "win32":
        appdata = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        return Path(appdata) / "Cursor" / "User" / "globalStorage" / "state.vscdb"
    if sys.platform == "darwin":
        return (
            Path.home()
            / "Library"
            / "Application Support"
            / "Cursor"
            / "User"
            / "globalStorage"
            / "state.vscdb"
        )
    xdg = os.environ.get("XDG_CONFIG_HOME")
    base = Path(xdg) if xdg else Path.home() / ".config"
    return base / "Cursor" / "User" / "globalStorage" / "state.vscdb"


def connect_readonly(path: Path) -> sqlite3.Connection:
    """Open a vscdb read-only. Copy to temp if the live file is locked."""
    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        raise FileNotFoundError(f"Cursor state.vscdb not found: {resolved}")
    uri = resolved.as_uri() + "?mode=ro"
    try:
        return sqlite3.connect(uri, uri=True, timeout=15)
    except sqlite3.OperationalError:
        import shutil
        import tempfile

        tmp = Path(tempfile.mkdtemp(prefix="juno-vscdb-")) / resolved.name
        shutil.copy2(resolved, tmp)
        wal = Path(str(resolved) + "-wal")
        shm = Path(str(resolved) + "-shm")
        if wal.is_file():
            shutil.copy2(wal, Path(str(tmp) + "-wal"))
        if shm.is_file():
            shutil.copy2(shm, Path(str(tmp) + "-shm"))
        return sqlite3.connect(tmp.as_uri() + "?mode=ro", uri=True, timeout=15)


def _tables(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    return {str(r[0]) for r in rows}


def _parse_json(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    if isinstance(value, memoryview):
        value = value.tobytes()
    if isinstance(value, bytes):
        value = value.decode("utf-8", errors="replace")
    text = str(value).strip()
    if not text:
        return {}
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _ms_or_iso(value: Any) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    if isinstance(value, (int, float)):
        ts = float(value)
        if ts > 10_000_000_000:
            ts /= 1000.0
        try:
            return datetime.fromtimestamp(ts, tz=UTC)
        except (OSError, OverflowError, ValueError):
            return None
    text = str(value).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _workspace_path(payload: dict[str, Any]) -> str | None:
    ident = payload.get("workspaceIdentifier")
    if isinstance(ident, dict):
        uri = ident.get("uri")
        if isinstance(uri, dict):
            fs_path = uri.get("fsPath") or uri.get("path")
            if fs_path:
                return str(fs_path)
        if ident.get("id"):
            pass
    repos = payload.get("trackedGitRepos")
    if isinstance(repos, list) and repos:
        first = repos[0]
        if isinstance(first, dict):
            path = first.get("repoPath") or first.get("path")
            if path:
                return str(path)
        elif isinstance(first, str):
            return first
    git = payload.get("gitWorktree")
    if isinstance(git, dict):
        path = git.get("worktreePath") or git.get("rootPath")
        if path:
            return str(path)
    return None


def _kv_get(conn: sqlite3.Connection, key: str) -> dict[str, Any]:
    row = conn.execute("SELECT value FROM cursorDiskKV WHERE key = ?", (key,)).fetchone()
    if not row:
        return {}
    return _parse_json(row[0])


def list_sessions(conn: sqlite3.Connection, *, include_archived: bool = False) -> list[CursorSession]:
    """Newest-first session metadata (bubbles not loaded)."""
    tables = _tables(conn)
    sessions: list[CursorSession] = []
    if "composerHeaders" in tables:
        rows = conn.execute(
            "SELECT composerId, workspaceId, createdAt, lastUpdatedAt, isArchived, value "
            "FROM composerHeaders ORDER BY lastUpdatedAt DESC"
        ).fetchall()
        for composer_id, workspace_id, created, updated, archived, value in rows:
            if archived and not include_archived:
                continue
            payload = _parse_json(value)
            sessions.append(
                CursorSession(
                    composer_id=str(composer_id),
                    name=str(payload.get("name") or "Untitled chat"),
                    created_at=_ms_or_iso(created or payload.get("createdAt")),
                    updated_at=_ms_or_iso(updated or payload.get("lastUpdatedAt")),
                    workspace_id=str(workspace_id) if workspace_id else None,
                    workspace_path=_workspace_path(payload),
                    mode=str(payload.get("unifiedMode") or payload.get("forceMode") or "") or None,
                )
            )
        return sessions

    item = None
    if "ItemTable" in tables:
        item = conn.execute(
            "SELECT value FROM ItemTable WHERE key = ?",
            ("composer.composerHeaders",),
        ).fetchone()
    if item:
        blob = _parse_json(item[0])
        for entry in blob.get("allComposers") or []:
            if not isinstance(entry, dict):
                continue
            if entry.get("isArchived") and not include_archived:
                continue
            ident = entry.get("workspaceIdentifier")
            workspace_id = None
            if isinstance(ident, dict):
                workspace_id = str(ident.get("id") or "") or None
            sessions.append(
                CursorSession(
                    composer_id=str(entry.get("composerId") or ""),
                    name=str(entry.get("name") or "Untitled chat"),
                    created_at=_ms_or_iso(entry.get("createdAt")),
                    updated_at=_ms_or_iso(entry.get("lastUpdatedAt")),
                    workspace_id=workspace_id,
                    workspace_path=_workspace_path(entry),
                    mode=str(entry.get("unifiedMode") or "") or None,
                )
            )
        sessions.sort(key=lambda s: s.updated_at or datetime.min.replace(tzinfo=UTC), reverse=True)
        return sessions

    rows = conn.execute(
        "SELECT key, value FROM cursorDiskKV WHERE key LIKE 'composerData:%'"
    ).fetchall()
    for key, value in rows:
        payload = _parse_json(value)
        composer_id = str(payload.get("composerId") or str(key).split(":", 1)[-1])
        sessions.append(
            CursorSession(
                composer_id=composer_id,
                name=str(payload.get("name") or "Untitled chat"),
                created_at=_ms_or_iso(payload.get("createdAt")),
                updated_at=_ms_or_iso(payload.get("lastUpdatedAt")),
                workspace_path=_workspace_path(payload),
                mode=str(payload.get("unifiedMode") or payload.get("forceMode") or "") or None,
            )
        )
    sessions.sort(key=lambda s: s.updated_at or datetime.min.replace(tzinfo=UTC), reverse=True)
    return sessions


def _bubble_text(bubble: dict[str, Any], header: dict[str, Any]) -> str:
    for key in ("text", "richText", "content"):
        val = bubble.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    grouping = header.get("grouping")
    if isinstance(grouping, dict):
        preview = grouping.get("textPreview")
        if isinstance(preview, str) and preview.strip():
            return preview.strip()
    return ""


def load_session(conn: sqlite3.Connection, composer_id: str) -> CursorSession | None:
    data = _kv_get(conn, f"composerData:{composer_id}")
    headers_meta = None
    tables = _tables(conn)
    if "composerHeaders" in tables:
        row = conn.execute(
            "SELECT workspaceId, createdAt, lastUpdatedAt, value FROM composerHeaders "
            "WHERE composerId = ?",
            (composer_id,),
        ).fetchone()
        if row:
            headers_meta = {
                "workspace_id": row[0],
                "created": row[1],
                "updated": row[2],
                "payload": _parse_json(row[3]),
            }
    if not data and headers_meta is None:
        return None

    payload = data or (headers_meta["payload"] if headers_meta else {})
    headers = payload.get("fullConversationHeadersOnly") or []
    bubbles: list[Bubble] = []
    for header in headers:
        if not isinstance(header, dict):
            continue
        bubble_id = str(header.get("bubbleId") or header.get("id") or "")
        if not bubble_id:
            continue
        raw = _kv_get(conn, f"bubbleId:{composer_id}:{bubble_id}")
        text = _bubble_text(raw, header)
        if not text:
            continue
        role_type = header.get("type")
        if role_type is None:
            role_type = raw.get("type")
        role = ROLE_BY_TYPE.get(int(role_type) if role_type is not None else 0, "assistant")
        created = _ms_or_iso(raw.get("createdAt") or header.get("createdAt"))
        bubbles.append(
            Bubble(
                bubble_id=bubble_id,
                role=role,
                text=text,
                created_at=_iso(created),
            )
        )

    name = str(payload.get("name") or (headers_meta or {}).get("payload", {}).get("name") or "Untitled chat")
    created_at = _ms_or_iso(payload.get("createdAt"))
    updated_at = _ms_or_iso(payload.get("lastUpdatedAt"))
    workspace_id = None
    workspace_path = _workspace_path(payload)
    if headers_meta:
        workspace_id = str(headers_meta["workspace_id"] or "") or None
        created_at = created_at or _ms_or_iso(headers_meta["created"])
        updated_at = updated_at or _ms_or_iso(headers_meta["updated"])
        workspace_path = workspace_path or _workspace_path(headers_meta["payload"])
        name = str(headers_meta["payload"].get("name") or name)

    return CursorSession(
        composer_id=composer_id,
        name=name,
        created_at=created_at,
        updated_at=updated_at,
        workspace_id=workspace_id,
        workspace_path=workspace_path,
        mode=str(payload.get("unifiedMode") or payload.get("forceMode") or "") or None,
        bubbles=tuple(bubbles),
    )


def format_session_text(session: CursorSession) -> str:
    lines = [session.name]
    if session.workspace_path:
        lines.append(f"Workspace: {session.workspace_path}")
    lines.append("")
    for bubble in session.bubbles:
        lines.append(f"{bubble.role}:")
        lines.append(bubble.text)
        lines.append("")
    return "\n".join(lines).strip()


def to_ingest_payload(session: CursorSession) -> dict[str, Any]:
    """Loopback ``POST /ingest`` body. HTTP client only — no SQLite/Chroma writes."""
    visited = _iso(session.updated_at or session.created_at) or datetime.now(UTC).isoformat()
    return {
        "source_type": "ide",
        "uri": session.uri,
        "title": session.name,
        "text": format_session_text(session),
        "visited_at": visited,
        "raw_json": {
            "kind": "cursor_chat",
            "composer_id": session.composer_id,
            "workspace_id": session.workspace_id,
            "workspace_path": session.workspace_path,
            "mode": session.mode,
            "created_at": _iso(session.created_at),
            "updated_at": _iso(session.updated_at),
            "bubbles": [
                {
                    "bubble_id": b.bubble_id,
                    "role": b.role,
                    "text": b.text,
                    "created_at": b.created_at,
                }
                for b in session.bubbles
            ],
        },
    }
