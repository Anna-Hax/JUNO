"""Full local export and wipe (data ownership — PRD §9)."""

from __future__ import annotations

import asyncio
import gc
import json
import shutil
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from juno.config import Settings
from juno.graph.db import Database
from juno.graph.vectors import VectorStore
from juno.llm.embedder import Embedder
from juno.models import (
    AppSetting,
    Capture,
    Chunk,
    Edge,
    ModuleHealth,
    Node,
    ReviewItem,
)

EXPORT_FORMAT = "juno-export"
EXPORT_VERSION = 1
WIPE_CONFIRM_PHRASE = "wipe-all-data"

TABLE_MODELS: tuple[tuple[str, type[Any]], ...] = (
    ("captures", Capture),
    ("nodes", Node),
    ("edges", Edge),
    ("chunks", Chunk),
    ("review_items", ReviewItem),
    ("module_health", ModuleHealth),
    ("settings", AppSetting),
)


def _serialize(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def _row_dict(row: Any) -> dict[str, Any]:
    return {col.name: _serialize(getattr(row, col.name)) for col in row.__table__.columns}


async def export_graph(db: Database) -> dict[str, list[dict[str, Any]]]:
    async def load(session: AsyncSession) -> dict[str, list[dict[str, Any]]]:
        out: dict[str, list[dict[str, Any]]] = {}
        for name, model in TABLE_MODELS:
            result = await session.execute(select(model))
            out[name] = [_row_dict(row) for row in result.scalars().all()]
        return out

    return await db.read(load)


async def build_export_payload(
    settings: Settings,
    *,
    db: Database,
    vectors: VectorStore | None = None,
    embedder: Embedder | None = None,
) -> dict[str, Any]:
    graph = await export_graph(db)
    vector_block: dict[str, Any] | None = None
    if vectors is not None:
        vector_block = await asyncio.to_thread(vectors.export_snapshot)

    live = embedder
    return {
        "format": EXPORT_FORMAT,
        "version": EXPORT_VERSION,
        "exported_at": datetime.now(UTC).isoformat(),
        "paths": {
            "sqlite": str(settings.sqlite_path),
            "chroma": str(settings.chroma_path),
        },
        "embedding": {
            "model": live.model_id if live is not None else settings.embedding_model,
            "backend": live.backend if live is not None else settings.embedding_backend,
            "dimensions": live.dimensions if live is not None else None,
        },
        "graph": graph,
        "vectors": vector_block,
    }


def default_export_path(settings: Settings) -> Path:
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return settings.juno_data_dir / f"juno-export-{stamp}.json"


def write_export_file(payload: dict[str, Any], path: Path) -> Path:
    path = path.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def _rmtree_with_retry(path: Path, *, attempts: int = 6) -> None:
    last: OSError | None = None
    for attempt in range(attempts):
        try:
            if path.exists():
                shutil.rmtree(path)
            return
        except OSError as exc:
            last = exc
            gc.collect()
            time.sleep(0.05 * (attempt + 1))
    if last is not None:
        raise last


async def wipe_local_data(settings: Settings, *, confirm: str) -> list[str]:
    if confirm != WIPE_CONFIRM_PHRASE:
        raise ValueError(
            f'Refuse wipe without --confirm "{WIPE_CONFIRM_PHRASE}" '
            "(this deletes the SQLite graph and all Chroma collections)."
        )

    removed: list[str] = []
    db = Database(settings)
    await db.dispose()

    sqlite = settings.sqlite_path
    if sqlite.exists():
        sqlite.unlink()
        removed.append(str(sqlite.resolve()))

    chroma = settings.chroma_path
    if chroma.exists():
        gc.collect()
        _rmtree_with_retry(chroma)
        removed.append(str(chroma.resolve()))

    settings.juno_data_dir.mkdir(parents=True, exist_ok=True)
    settings.chroma_path.mkdir(parents=True, exist_ok=True)

    fresh = Database(settings)
    await fresh.migrate()
    await fresh.dispose()
    return removed
