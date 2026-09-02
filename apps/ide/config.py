"""IDE adapter settings from env / .env (HTTP client — not juno Settings)."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path


def default_global_vscdb() -> Path:
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


def default_workspace_storage() -> Path:
    return default_global_vscdb().parent.parent / "workspaceStorage"


def resolve_env_file(*, start: Path | None = None) -> Path | None:
    if start is not None:
        candidate = start.resolve() / ".env"
        return candidate if candidate.is_file() else None
    here = Path.cwd().resolve()
    for base in (here, *here.parents):
        candidate = base / ".env"
        if candidate.is_file():
            return candidate
    return None


def _load_dotenv(path: Path) -> dict[str, str]:
    loaded: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        if key:
            loaded[key] = value
    return loaded


def _env(mapping: dict[str, str], key: str, default: str = "") -> str:
    return (os.environ.get(key) or mapping.get(key) or default).strip()


@dataclass(frozen=True)
class IdeConfig:
    api_base_url: str
    api_token: str
    global_vscdb: Path
    workspace_storage: Path
    poll_seconds: float
    state_path: Path
    workspace_filter: str | None = None

    def token_is_usable(self) -> bool:
        token = self.api_token.strip().lower()
        return bool(token) and token != "change-me"


def load_config(*, start: Path | None = None) -> IdeConfig:
    """Resolve Cursor paths + loopback API settings. Env wins over .env."""
    file_vals: dict[str, str] = {}
    env_path = resolve_env_file(start=start)
    if env_path is not None:
        file_vals = _load_dotenv(env_path)

    host = _env(file_vals, "JUNO_API_HOST", "127.0.0.1") or "127.0.0.1"
    port = _env(file_vals, "JUNO_API_PORT", "8787") or "8787"
    base = _env(file_vals, "JUNO_API_BASE_URL") or f"http://{host}:{port}"

    vscdb = _env(file_vals, "JUNO_CURSOR_VSCDB")
    workspace = _env(file_vals, "JUNO_CURSOR_WORKSPACE_STORAGE")
    data_dir = _env(file_vals, "JUNO_DATA_DIR", "./data") or "./data"
    state = _env(file_vals, "JUNO_IDE_STATE")
    poll = _env(file_vals, "JUNO_IDE_POLL_SECONDS", "60") or "60"
    filt = _env(file_vals, "JUNO_CURSOR_WORKSPACE") or None

    return IdeConfig(
        api_base_url=base.rstrip("/"),
        api_token=_env(file_vals, "JUNO_API_TOKEN"),
        global_vscdb=Path(vscdb).expanduser() if vscdb else default_global_vscdb(),
        workspace_storage=(
            Path(workspace).expanduser() if workspace else default_workspace_storage()
        ),
        poll_seconds=max(5.0, float(poll)),
        state_path=Path(state).expanduser() if state else Path(data_dir) / "ide-adapter.json",
        workspace_filter=filt,
    )
