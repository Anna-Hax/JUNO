"""CLI entrypoints."""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="juno", description="Juno personal knowledge graph")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("serve", help="Start API + Telegram bot (shared event loop)")
    sub.add_parser("db-init", help="Create or upgrade SQLite schema (Alembic)")

    export_p = sub.add_parser("export", help="Export graph + vectors to JSON")
    export_p.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Output path (default: data/juno-export-<timestamp>.json)",
    )

    wipe_p = sub.add_parser("wipe", help="Delete local graph + vectors")
    wipe_p.add_argument(
        "--confirm",
        required=True,
        help='Must be exactly "wipe-all-data"',
    )

    prune_p = sub.add_parser(
        "prune",
        help="Queue HITL prune of old/unused captures (never silent delete)",
    )
    prune_p.add_argument(
        "--days",
        type=int,
        default=None,
        help="Minimum age in days for unused captures (default: JUNO_PRUNE_MIN_AGE_DAYS)",
    )
    prune_p.add_argument(
        "-o",
        "--export",
        type=Path,
        default=None,
        help="Optional JSON export path written before queueing (full graph, same as juno export)",
    )
    prune_p.add_argument(
        "--confirm",
        default="",
        help='Must be exactly "prune-selected" to queue /review; omit for dry-run',
    )

    sub.add_parser("version", help="Print version")

    args = parser.parse_args(argv)

    if args.command == "version" or args.command is None and argv == []:
        from juno import __version__

        print(__version__)
        if args.command is None:
            parser.print_help()
        return

    if args.command is None:
        # Default: serve
        from juno.runtime import main_sync

        main_sync()
        return

    if args.command == "serve":
        from juno.runtime import main_sync

        main_sync()
        return

    if args.command == "db-init":
        asyncio.run(_db_init())
        return

    if args.command == "export":
        asyncio.run(_export(args.output))
        return

    if args.command == "wipe":
        asyncio.run(_wipe(args.confirm))
        return

    if args.command == "prune":
        asyncio.run(_prune(days=args.days, confirm=args.confirm, export_path=args.export))
        return

    parser.print_help()
    sys.exit(1)


async def _db_init() -> None:
    from juno.config import get_settings
    from juno.graph.db import Database

    settings = get_settings()
    db = Database(settings)
    action = await db.migrate()
    await db.dispose()
    print(f"Initialized database at {settings.sqlite_path} (alembic {action})")


async def _export(output: Path | None) -> None:
    from juno.config import get_settings
    from juno.graph.db import Database
    from juno.graph.ownership import (
        build_export_payload,
        default_export_path,
        write_export_file,
    )
    from juno.graph.vectors import VectorStore
    from juno.llm.embedder import create_embedder

    settings = get_settings()
    db = Database(settings)
    await db.migrate()
    try:
        try:
            embedder = create_embedder(settings.embedding_backend, settings.embedding_model)
        except Exception:
            embedder = create_embedder("stub", settings.embedding_model)
        vectors = VectorStore(settings, embedder)
        payload = await build_export_payload(
            settings,
            db=db,
            vectors=vectors,
            embedder=embedder,
        )
        dest = write_export_file(payload, output or default_export_path(settings))
        n_cap = len(payload["graph"]["captures"])
        n_vec = int((payload.get("vectors") or {}).get("count") or 0)
        print(f"Exported {n_cap} captures and {n_vec} vectors to {dest}")
    finally:
        vectors.close()
        await db.dispose()


async def _wipe(confirm: str) -> None:
    from juno.config import get_settings
    from juno.graph.ownership import wipe_local_data

    settings = get_settings()
    try:
        removed = await wipe_local_data(settings, confirm=confirm)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)
    print(f"Wiped {len(removed)} path(s); empty schema at {settings.sqlite_path}")
    for path in removed:
        print(f"  removed {path}")


async def _prune(
    days: int | None,
    confirm: str,
    export_path: Path | None,
) -> None:
    from juno.config import get_settings
    from juno.graph.db import Database
    from juno.graph.ownership import build_export_payload, write_export_file
    from juno.graph.prune import (
        DEFAULT_MIN_AGE_DAYS,
        PRUNE_CONFIRM_PHRASE,
        format_candidates,
        list_prune_candidates,
        propose_prune,
    )
    from juno.graph.vectors import VectorStore
    from juno.llm.embedder import create_embedder

    settings = get_settings()
    age = settings.juno_prune_min_age_days or DEFAULT_MIN_AGE_DAYS
    min_days = int(days if days is not None else age)
    db = Database(settings)
    await db.migrate()
    vectors = None
    try:
        candidates = await list_prune_candidates(db, min_age_days=min_days)
        print(format_candidates(candidates, min_age_days=min_days))
        if not confirm:
            print("Dry-run only. Re-run with --confirm prune-selected to queue HITL.")
            return
        if confirm != PRUNE_CONFIRM_PHRASE:
            print(
                f'Refuse prune queue without --confirm "{PRUNE_CONFIRM_PHRASE}" '
                "(this still does not delete; Approve in /review archives).",
                file=sys.stderr,
            )
            sys.exit(1)
        exported = None
        if export_path is not None:
            try:
                embedder = create_embedder(settings.embedding_backend, settings.embedding_model)
            except Exception:
                embedder = create_embedder("stub", settings.embedding_model)
            vectors = VectorStore(settings, embedder)
            payload = await build_export_payload(
                settings, db=db, vectors=vectors, embedder=embedder
            )
            dest = write_export_file(payload, export_path)
            exported = str(dest)
            print(f"Export written to {dest}")
        if not candidates:
            return
        card = await propose_prune(db, candidates=candidates, exported_path=exported)
        if card is None:
            print("Already queued in /review. Nothing deleted.")
            return
        print(
            f"Queued prune review #{card.id} "
            f"({len(card.payload.get('capture_ids') or [])} capture(s)). "
            "Approve in Telegram /review to archive. Not a wipe."
        )
    finally:
        if vectors is not None:
            vectors.close()
        await db.dispose()


if __name__ == "__main__":
    main()
