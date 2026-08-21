"""Alembic helpers: upgrade head, stamp legacy create_all databases."""

from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

LEGACY_GRAPH_TABLE = "captures"


def alembic_ini_path() -> Path:
    start = Path(__file__).resolve()
    for parent in [start.parent, *start.parents]:
        candidate = parent / "alembic.ini"
        if candidate.is_file():
            return candidate
    raise FileNotFoundError("alembic.ini not found (expected under apps/core/)")


def sync_sqlite_url(sqlite_path: Path) -> str:
    sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{sqlite_path.as_posix()}"


def make_alembic_config(sync_url: str) -> Config:
    ini = alembic_ini_path()
    root = ini.parent
    cfg = Config(str(ini))
    cfg.set_main_option("sqlalchemy.url", sync_url)
    cfg.set_main_option("script_location", str((root / "alembic").resolve()))
    # Absolute so `juno db-init` works regardless of process cwd.
    cfg.set_main_option("prepend_sys_path", str((root / "src").resolve()))
    return cfg


def is_legacy_unstamped(sync_url: str) -> bool:
    """True when tables exist from create_all but Alembic has never stamped the file."""
    engine = create_engine(sync_url)
    try:
        with engine.connect() as conn:
            names = set(inspect(conn).get_table_names())
    finally:
        engine.dispose()
    if "alembic_version" in names:
        return False
    return LEGACY_GRAPH_TABLE in names


def upgrade_to_head(sqlite_path: Path) -> str:
    """Apply migrations, or stamp head on a pre-Alembic create_all database.

    Returns ``upgrade`` or ``stamp``.
    """
    url = sync_sqlite_url(sqlite_path)
    cfg = make_alembic_config(url)
    if is_legacy_unstamped(url):
        command.stamp(cfg, "head")
        return "stamp"
    command.upgrade(cfg, "head")
    return "upgrade"
