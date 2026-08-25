"""Local FastAPI surface — loopback only, token-gated."""

from __future__ import annotations

import asyncio
import hmac
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import JSONResponse

from juno.config import Settings, api_token_is_configured, is_loopback_client_host
from juno.rag.engine import search as rag_search

_AUTH_DETAIL = "Invalid or missing API token"


def _bearer_token(authorization: str | None) -> str:
    if not authorization:
        return ""
    scheme, _, remainder = authorization.partition(" ")
    if scheme.lower() != "bearer":
        return ""
    return remainder.strip()


def token_matches(provided: str, expected: str) -> bool:
    if not provided or not api_token_is_configured(expected):
        return False
    return hmac.compare_digest(provided, expected.strip())


def create_app(
    settings: Settings,
    *,
    db: Any = None,
    embedder: Any = None,
    vectors: Any = None,
    pipeline: Any = None,
    chat: Any = None,
) -> FastAPI:
    app = FastAPI(
        title="Juno",
        version="0.1.0",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.state.settings = settings
    app.state.db = db
    app.state.embedder = embedder
    app.state.vectors = vectors
    app.state.chat = chat
    app.state.capture_paused = False
    app.state.llm_healthy = False
    if pipeline is not None:
        app.state.pipeline = pipeline
    elif db is not None:
        from juno.ingest.pipeline import IngestPipeline

        app.state.pipeline = IngestPipeline(db=db, vectors=vectors)
    else:
        app.state.pipeline = None

    def require_token(authorization: str | None = Header(default=None)) -> None:
        expected = settings.juno_api_token
        if not token_matches(_bearer_token(authorization), expected):
            raise HTTPException(status_code=401, detail=_AUTH_DETAIL)

    @app.middleware("http")
    async def loopback_only(request: Request, call_next):  # noqa: ANN001
        client = request.client.host if request.client else ""
        if not is_loopback_client_host(client):
            return JSONResponse(status_code=403, content={"detail": "Loopback only"})
        return await call_next(request)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/status", dependencies=[Depends(require_token)])
    async def status() -> dict[str, Any]:
        embedder = app.state.embedder
        vectors = app.state.vectors
        chat = getattr(app.state, "chat", None)
        chroma_count = 0
        if vectors is not None:
            chroma_count = await asyncio.to_thread(vectors.count)

        llm_healthy = bool(getattr(app.state, "llm_healthy", False))
        llm_provider = getattr(chat, "name", None) or settings.llm_provider
        llm_model = getattr(chat, "model", None) or settings.llm_model
        if chat is not None:
            llm_healthy = await chat.healthy(timeout=1.5)
            app.state.llm_healthy = llm_healthy

        actual_backend = (
            getattr(embedder, "backend", settings.embedding_backend)
            if embedder is not None
            else settings.embedding_backend
        )
        return {
            "capture_paused": app.state.capture_paused,
            "llm_healthy": llm_healthy,
            "llm_provider": llm_provider,
            "llm_model": llm_model,
            "embedding_model": getattr(embedder, "model_id", settings.embedding_model),
            "embedding_backend": actual_backend,
            "embedding_dimensions": getattr(embedder, "dimensions", None),
            "embedding_fallback": bool(
                embedder is not None and actual_backend != settings.embedding_backend
            ),
            "chroma_collection": getattr(vectors, "collection_name", None),
            "chroma_count": chroma_count,
            "api_host": settings.juno_api_host,
            "api_port": settings.juno_api_port,
        }

    @app.post("/ingest", dependencies=[Depends(require_token)])
    async def ingest(payload: dict[str, Any]) -> dict[str, Any]:
        if app.state.capture_paused:
            raise HTTPException(status_code=423, detail="Capture paused")
        pipeline = app.state.pipeline
        if pipeline is None:
            raise HTTPException(status_code=503, detail="Ingest pipeline not ready")
        result = await pipeline.ingest_payload(payload)
        return result.to_dict()

    @app.get("/search", dependencies=[Depends(require_token)])
    async def search(
        q: str = Query(..., min_length=1),
        k: int = Query(8, ge=1, le=32),
        mode: str = Query("auto"),
    ) -> dict[str, Any]:
        outcome = await rag_search(
            q,
            vectors=app.state.vectors,
            db=app.state.db,
            chat=getattr(app.state, "chat", None),
            n_results=k,
            mode=mode,
        )
        return outcome.to_dict()

    return app
