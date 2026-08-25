from __future__ import annotations

import pytest
from alembic.autogenerate import compare_metadata
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, select, text

from juno.cli import _db_init
from juno.graph.db import Database
from juno.graph.migrations import (
    is_legacy_unstamped,
    make_alembic_config,
    sync_sqlite_url,
    upgrade_to_head,
)
from juno.models import Base, Capture

GRAPH_TABLES = {
    "captures",
    "nodes",
    "edges",
    "chunks",
    "review_items",
    "module_health",
    "settings",
}


def _table_names(sqlite_path) -> set[str]:
    engine = create_engine(sync_sqlite_url(sqlite_path))
    try:
        return set(inspect(engine).get_table_names())
    finally:
        engine.dispose()


def test_upgrade_creates_graph_tables(settings):
    assert upgrade_to_head(settings.sqlite_path) == "upgrade"
    names = _table_names(settings.sqlite_path)
    assert GRAPH_TABLES <= names
    assert "alembic_version" in names


@pytest.mark.asyncio
async def test_migrate_is_idempotent(settings):
    db = Database(settings)
    assert await db.migrate() == "upgrade"
    assert await db.migrate() == "upgrade"
    await db.dispose()


@pytest.mark.asyncio
async def test_legacy_create_all_is_stamped(settings):
    db = Database(settings)
    await db.create_all()
    url = sync_sqlite_url(settings.sqlite_path)
    assert is_legacy_unstamped(url)

    assert await db.migrate() == "stamp"
    assert not is_legacy_unstamped(url)

    async def insert(session):
        session.add(Capture(source_type="upload", text="legacy row", status="committed"))

    await db.write(insert)

    async def count(session):
        result = await session.execute(select(Capture))
        return list(result.scalars())

    rows = await db.read(count)
    assert len(rows) == 1
    await db.dispose()


def test_head_matches_orm_metadata(settings):
    upgrade_to_head(settings.sqlite_path)
    engine = create_engine(sync_sqlite_url(settings.sqlite_path))
    try:
        with engine.connect() as conn:
            ctx = MigrationContext.configure(
                connection=conn,
                opts={"compare_type": True, "render_as_batch": True},
            )
            diffs = compare_metadata(ctx, Base.metadata)
    finally:
        engine.dispose()
    assert diffs == [], diffs


@pytest.mark.asyncio
async def test_db_init_cli(settings, monkeypatch, capsys):
    monkeypatch.setattr("juno.config.get_settings", lambda: settings)
    await _db_init()
    assert settings.sqlite_path.exists()
    out = capsys.readouterr().out
    assert "Initialized database" in out
    assert "alembic upgrade" in out

    url = sync_sqlite_url(settings.sqlite_path)
    engine = create_engine(url)
    try:
        with engine.connect() as conn:
            version = conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
    finally:
        engine.dispose()
    head = ScriptDirectory.from_config(make_alembic_config(url)).get_current_head()
    assert version == head
