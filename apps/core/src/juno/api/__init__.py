"""Local FastAPI surface — loopback only, token-gated."""

from __future__ import annotations

from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse

from juno.config import Settings


def create_app(settings: Settings, *, db: Any = None, embedder: Any = None) -> FastAPI:
    app = FastAPI(title="Juno", version="0.1.0")
    app.state.settings = settings
    app.state.db = db
    app.state.embedder = embedder
    app.state.capture_paused = False
    app.state.llm_healthy = False

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
        return {
            "capture_paused": app.state.capture_paused,
            "llm_healthy": app.state.llm_healthy,
            "embedding_model": settings.embedding_model,
            "embedding_backend": settings.embedding_backend,
            "api_host": settings.juno_api_host,
            "api_port": settings.juno_api_port,
        }

    @app.post("/ingest", dependencies=[Depends(require_token)])
    async def ingest(payload: dict[str, Any]) -> dict[str, Any]:
        if app.state.capture_paused:
            raise HTTPException(status_code=423, detail="Capture paused")
        # Full ingest wired in later milestones; acknowledge payload shape
        return {"accepted": True, "source_type": payload.get("source_type", "api")}

    @app.get("/search", dependencies=[Depends(require_token)])
    async def search(q: str) -> dict[str, Any]:
        return {"query": q, "results": [], "note": "RAG retrieve not fully wired yet"}

    return app
