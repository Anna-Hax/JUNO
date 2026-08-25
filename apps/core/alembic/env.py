"""Alembic environment.

Migrations use **sync** SQLite (`sqlite:///`) so `alembic upgrade` can run from
`juno serve` / `db-init` without nesting an asyncio loop (ADR-01 / ADR-03).
Runtime traffic still goes through `sqlite+aiosqlite`.
"""

from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine

from juno.models import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata

_PLACEHOLDER_URLS = {"", "driver://user:pass@localhost/dbname"}


def _database_url() -> str:
    url = (config.get_main_option("sqlalchemy.url") or "").strip()
    if url and url not in _PLACEHOLDER_URLS:
        return url
    from juno.config import get_settings

    settings = get_settings()
    settings.juno_data_dir.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{settings.sqlite_path.as_posix()}"


def run_migrations_offline() -> None:
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = create_engine(_database_url())
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()
    connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
