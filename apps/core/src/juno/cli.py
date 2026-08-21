"""CLI entrypoints."""

from __future__ import annotations

import argparse
import asyncio
import sys


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="juno", description="Juno personal knowledge graph")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("serve", help="Start API + Telegram bot (shared event loop)")
    sub.add_parser("db-init", help="Create or upgrade SQLite schema (Alembic)")
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


if __name__ == "__main__":
    main()
