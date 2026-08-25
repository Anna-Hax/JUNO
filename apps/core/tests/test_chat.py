from __future__ import annotations

from typing import Any

import httpx
import pytest

from juno.graph.db import Database
from juno.llm.chat import (
    OfflineProvider,
    OllamaProvider,
    OpenAICompatProvider,
    _ollama_model_present,
    create_chat_provider,
)
from juno.models import ModuleHealth
from juno.runtime import persist_llm_health

_RealAsyncClient = httpx.AsyncClient


def _patch_client(monkeypatch: pytest.MonkeyPatch, handler):
    def factory(*args: Any, **kwargs: Any) -> httpx.AsyncClient:
        def transport_handler(request: httpx.Request) -> httpx.Response:
            headers = dict(request.headers)
            return handler(request.method, str(request.url), headers=headers)

        kwargs["transport"] = httpx.MockTransport(transport_handler)
        return _RealAsyncClient(*args, **kwargs)

    monkeypatch.setattr("juno.llm.chat.httpx.AsyncClient", factory)


def test_create_chat_provider_switches_on_name():
    ollama = create_chat_provider(
        "ollama",
        ollama_base_url="http://127.0.0.1:11434",
        ollama_model="llama3.2",
        openai_base_url="https://api.openai.com/v1",
        openai_api_key="sk-test",
        openai_model="gpt-4o-mini",
    )
    assert isinstance(ollama, OllamaProvider)
    assert ollama.model == "llama3.2"

    openai = create_chat_provider(
        "openai_compat",
        ollama_base_url="http://127.0.0.1:11434",
        ollama_model="llama3.2",
        openai_base_url="http://127.0.0.1:1234/v1",
        openai_api_key="local",
        openai_model="local-model",
    )
    assert isinstance(openai, OpenAICompatProvider)
    assert openai.model == "local-model"

    offline = create_chat_provider(
        "offline",
        ollama_base_url="http://127.0.0.1:11434",
        ollama_model="llama3.2",
        openai_base_url="https://api.openai.com/v1",
        openai_api_key="",
        openai_model="gpt-4o-mini",
    )
    assert isinstance(offline, OfflineProvider)


def test_create_chat_provider_unknown():
    with pytest.raises(ValueError, match="Unknown LLM provider"):
        create_chat_provider(
            "anthropic",
            ollama_base_url="",
            ollama_model="",
            openai_base_url="",
            openai_api_key="",
            openai_model="",
        )


def test_ollama_model_present_matches_tags():
    names = ["llama3.2:latest", "nomic-embed-text:latest"]
    assert _ollama_model_present(names, "llama3.2") is True
    assert _ollama_model_present(names, "llama3.2:latest") is True
    assert _ollama_model_present(names, "mistral") is False


@pytest.mark.asyncio
async def test_ollama_healthy_when_model_listed(monkeypatch):
    def handler(method: str, url: str, **kwargs: Any) -> httpx.Response:
        assert method == "GET"
        assert url.endswith("/api/tags")
        return httpx.Response(200, json={"models": [{"name": "llama3.2:latest"}]})

    _patch_client(monkeypatch, handler)
    assert await OllamaProvider("http://127.0.0.1:11434", "llama3.2").healthy() is True


@pytest.mark.asyncio
async def test_ollama_unhealthy_when_down(monkeypatch):
    def handler(method: str, url: str, **kwargs: Any) -> httpx.Response:
        raise RuntimeError("offline")

    _patch_client(monkeypatch, handler)
    assert await OllamaProvider("http://127.0.0.1:11434", "llama3.2").healthy() is False


@pytest.mark.asyncio
async def test_ollama_complete(monkeypatch):
    def handler(method: str, url: str, **kwargs: Any) -> httpx.Response:
        assert method == "POST"
        assert url.endswith("/api/chat")
        return httpx.Response(200, json={"message": {"content": "hello graph"}})

    _patch_client(monkeypatch, handler)
    text = await OllamaProvider("http://127.0.0.1:11434", "llama3.2").complete(
        "sys", [{"role": "user", "content": "hi"}]
    )
    assert text == "hello graph"


@pytest.mark.asyncio
async def test_openai_healthy_requires_key_and_models():
    assert (
        await OpenAICompatProvider("https://api.openai.com/v1", "", "gpt-4o-mini").healthy()
        is False
    )


@pytest.mark.asyncio
async def test_openai_healthy_models_ok(monkeypatch):
    def handler(method: str, url: str, **kwargs: Any) -> httpx.Response:
        assert method == "GET"
        assert url.endswith("/models")
        auth = kwargs["headers"].get("Authorization") or kwargs["headers"].get("authorization")
        assert auth == "Bearer sk-test"
        return httpx.Response(200, json={"data": []})

    _patch_client(monkeypatch, handler)
    assert (
        await OpenAICompatProvider("https://api.openai.com/v1", "sk-test", "gpt-4o-mini").healthy()
        is True
    )


@pytest.mark.asyncio
async def test_openai_healthy_404_compat(monkeypatch):
    def handler(method: str, url: str, **kwargs: Any) -> httpx.Response:
        return httpx.Response(404)

    _patch_client(monkeypatch, handler)
    assert await OpenAICompatProvider("http://127.0.0.1:1234/v1", "local", "m").healthy() is True


@pytest.mark.asyncio
async def test_offline_fallback():
    chat = OfflineProvider()
    assert await chat.healthy() is False
    with pytest.raises(RuntimeError, match="retrieve-only"):
        await chat.complete("sys", [{"role": "user", "content": "q"}])


@pytest.mark.asyncio
async def test_persist_llm_health(settings):
    db = Database(settings)
    await db.create_all()
    chat = OfflineProvider()
    await persist_llm_health(db, chat, ok=False)

    async def fetch(session):
        return await session.get(ModuleHealth, "llm")

    row = await db.read(fetch)
    assert row is not None
    assert row.last_error == "health probe failed"
    assert row.detail == "offline"
    await db.dispose()


def test_status_live_llm_probe(settings):
    from fastapi.testclient import TestClient

    from juno.api import create_app

    class FakeChat:
        name = "ollama"
        model = "llama3.2"
        calls = 0

        async def healthy(self, *, timeout: float = 3.0) -> bool:
            self.calls += 1
            return True

    chat = FakeChat()
    app = create_app(settings, chat=chat)
    client = TestClient(app)
    body = client.get("/status", headers={"Authorization": "Bearer test-token"}).json()
    assert body["llm_healthy"] is True
    assert body["llm_provider"] == "ollama"
    assert body["llm_model"] == "llama3.2"
    assert chat.calls == 1
