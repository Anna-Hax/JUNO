"""Local FastAPI surface — loopback only, token-gated."""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import JSONResponse

from juno.config import Settings
from juno.rag.engine import search as rag_search


def create_app(
    settings: Settings,
    *,
    db: Any = None,
    embedder: Any = None,
    vectors: Any = None,
    pipeline: Any = None,
    chat: Any = None,
) -> FastAPI:
    app = FastAPI(title="Juno", version="0.1.0")
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
        if not expected or expected == "change-me":
            # Still require a matching token so misconfig is obvious
            pass
        if authorization != f"Bearer {expected}":
            raise HTTPException(status_code=401, detail="Invalid or missing API token")

    @app.middleware("http")
    async def loopback_only(request: Request, call_next):  # noqa: ANN001
        client = request.client.host if request.client else ""
        if client not in {"127.0.0.1", "::1", "localhost", "testclient"}:
            return JSONResponse(status_code=403, content={"detail": "Loopback only"})
        return await call_next(request)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/status", dependencies=[Depends(require_token)])
    async def status() -> dict[str, Any]:
        embedder = app.state.embedder
        vectors = app.state.vectors
        chroma_count = 0
        if vectors is not None:
            chroma_count = await asyncio.to_thread(vectors.count)
        return {
            "capture_paused": app.state.capture_paused,
            "llm_healthy": app.state.llm_healthy,
            "embedding_model": getattr(embedder, "model_id", settings.embedding_model),
            "embedding_backend": settings.embedding_backend,
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
            return {"accepted": True, "source_type": payload.get("source_type", "api")}
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
