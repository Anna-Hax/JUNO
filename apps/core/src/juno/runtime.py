"""Shared asyncio runtime: FastAPI (uvicorn) + Telegram PTB (manual lifecycle).

ADR-01: never call Application.run_polling() — it blocks and fights uvicorn.
Use Application.initialize/start + updater.start_polling inside FastAPI lifespan.
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import UTC, datetime

import uvicorn
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession
from telegram.ext import Application, CommandHandler, MessageHandler, filters

from juno.api import create_app
from juno.bot.handlers import help_cmd, start_cmd, text_query
from juno.config import Settings, get_settings
from juno.graph.db import Database
from juno.graph.vectors import VectorStore
from juno.ingest.pipeline import IngestPipeline
from juno.ingest.watcher import InboxWatcher
from juno.llm.chat import ChatProvider, create_chat_provider
from juno.llm.embedder import Embedder, create_embedder
from juno.models import AppSetting, ModuleHealth

logger = logging.getLogger("juno.runtime")


def build_telegram_application(settings: Settings) -> Application | None:
    if not settings.telegram_bot_token:
        logger.warning("TELEGRAM_BOT_TOKEN empty — bot disabled")
        return None

    app = Application.builder().token(settings.telegram_bot_token).build()
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_query))
    return app


async def persist_embedder_settings(db: Database, embedder: Embedder) -> None:
    """Record the live embedding model id so a later reindex can see what was used."""

    async def write(session: AsyncSession) -> None:
        pairs = {
            "embedding_model": embedder.model_id,
            "embedding_backend": embedder.backend,
            "embedding_dimensions": str(embedder.dimensions),
        }
        for key, value in pairs.items():
            row = await session.get(AppSetting, key)
            if row is None:
                session.add(AppSetting(key=key, value=value))
            else:
                row.value = value

    await db.write(write)


async def persist_llm_health(db: Database, chat: ChatProvider, *, ok: bool) -> None:
    async def write(session: AsyncSession) -> None:
        row = await session.get(ModuleHealth, "llm")
        if row is None:
            row = ModuleHealth(module="llm")
            session.add(row)
        now = datetime.now(UTC)
        row.detail = f"{chat.name}:{chat.model}" if chat.model else chat.name
        if ok:
            row.last_success_at = now
            row.last_error = None
        else:
            row.last_error_at = now
            row.last_error = "health probe failed"

    await db.write(write)


def attach_lifespan(fastapi_app: FastAPI) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        settings: Settings = app.state.settings
        db: Database = app.state.db
        await db.migrate()

        embedder: Embedder | None = getattr(app.state, "embedder", None)
        if embedder is not None:
            await persist_embedder_settings(db, embedder)

        chat = create_chat_provider(
            settings.llm_provider,
            ollama_base_url=settings.ollama_base_url,
            ollama_model=settings.ollama_model,
            openai_base_url=settings.openai_base_url,
            openai_api_key=settings.openai_api_key,
            openai_model=settings.openai_model,
        )
        llm_healthy = await chat.healthy()
        if not llm_healthy:
            logger.warning(
                "LLM provider %s is unhealthy — /status will keep probing; "
                "answers should use retrieve-only fallback",
                chat.name,
            )
        app.state.llm_healthy = llm_healthy
        app.state.chat = chat
        await persist_llm_health(db, chat, ok=llm_healthy)

        pipeline = getattr(app.state, "pipeline", None)
        if pipeline is not None:
            watcher = InboxWatcher(
                settings.juno_inbox_dir,
                pipeline.ingest_path,
                is_paused=lambda: bool(app.state.capture_paused),
            )
            await watcher.start()
            app.state.inbox_watcher = watcher

        ptb: Application | None = app.state.ptb
        if ptb is not None:
            await ptb.initialize()
            await ptb.start()
            if ptb.updater is not None:
                await ptb.updater.start_polling(drop_pending_updates=False)
            logger.info("Telegram bot polling started")

        yield

        watcher = getattr(app.state, "inbox_watcher", None)
        if watcher is not None:
            await watcher.stop()

        if ptb is not None:
            if ptb.updater is not None:
                await ptb.updater.stop()
            await ptb.stop()
            await ptb.shutdown()
            logger.info("Telegram bot stopped")
        await db.dispose()

    fastapi_app.router.lifespan_context = lifespan
    return fastapi_app


async def run_server(settings: Settings | None = None) -> None:
    settings = settings or get_settings()
    settings.juno_data_dir.mkdir(parents=True, exist_ok=True)
    settings.juno_inbox_dir.mkdir(parents=True, exist_ok=True)

    db = Database(settings)
    try:
        embedder = create_embedder(settings.embedding_backend, settings.embedding_model)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Falling back to stub embedder: %s", exc)
        embedder = create_embedder("stub", settings.embedding_model)

    vectors = VectorStore(settings, embedder)
    pipeline = IngestPipeline(db=db, vectors=vectors)
    fastapi_app = create_app(
        settings,
        db=db,
        embedder=embedder,
        vectors=vectors,
        pipeline=pipeline,
    )
    fastapi_app.state.settings = settings
    fastapi_app.state.db = db
    fastapi_app.state.embedder = embedder
    fastapi_app.state.vectors = vectors
    fastapi_app.state.pipeline = pipeline
    fastapi_app.state.ptb = build_telegram_application(settings)
    attach_lifespan(fastapi_app)

    config = uvicorn.Config(
        fastapi_app,
        host=settings.juno_api_host,
        port=settings.juno_api_port,
        log_level="info",
        loop="asyncio",
    )
    server = uvicorn.Server(config)
    await server.serve()


def main_sync() -> None:
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_server())
