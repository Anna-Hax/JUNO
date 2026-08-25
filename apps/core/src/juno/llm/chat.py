"""Chat LLM providers with health probes."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

import httpx


def _ollama_model_present(names: list[str], want: str) -> bool:
    """True if Ollama's /api/tags list includes the configured model (tag optional)."""
    want = (want or "").strip()
    if not want:
        return False
    want_base = want.split(":", 1)[0]
    for name in names:
        raw = (name or "").strip()
        if not raw:
            continue
        if raw == want or raw.startswith(f"{want}:"):
            return True
        if raw.split(":", 1)[0] == want_base:
            return True
    return False


class ChatProvider(ABC):
    name: str
    model: str

    @abstractmethod
    async def complete(
        self,
        system: str,
        messages: list[dict[str, str]],
        *,
        timeout: float = 15.0,
    ) -> str:
        raise NotImplementedError

    @abstractmethod
    async def healthy(self, *, timeout: float = 3.0) -> bool:
        raise NotImplementedError


class OllamaProvider(ChatProvider):
    name = "ollama"

    def __init__(self, base_url: str, model: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model

    async def complete(
        self,
        system: str,
        messages: list[dict[str, str]],
        *,
        timeout: float = 15.0,
    ) -> str:
        payload = {
            "model": self.model,
            "stream": False,
            "messages": [{"role": "system", "content": system}, *messages],
        }
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(f"{self.base_url}/api/chat", json=payload)
            resp.raise_for_status()
            data: dict[str, Any] = resp.json()
            return str(data.get("message", {}).get("content", ""))

    async def healthy(self, *, timeout: float = 3.0) -> bool:
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.get(f"{self.base_url}/api/tags")
                if resp.status_code != 200:
                    return False
                models = resp.json().get("models") or []
                names = [str(m.get("name", "")) for m in models if isinstance(m, dict)]
                return _ollama_model_present(names, self.model)
        except Exception:
            return False


class OpenAICompatProvider(ChatProvider):
    name = "openai_compat"

    def __init__(self, base_url: str, api_key: str, model: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model

    async def complete(
        self,
        system: str,
        messages: list[dict[str, str]],
        *,
        timeout: float = 15.0,
    ) -> str:
        headers = {"Authorization": f"Bearer {self.api_key}"}
        payload = {
            "model": self.model,
            "messages": [{"role": "system", "content": system}, *messages],
        }
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
            return str(data["choices"][0]["message"]["content"])

    async def healthy(self, *, timeout: float = 3.0) -> bool:
        if not self.api_key:
            return False
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.get(
                    f"{self.base_url}/models",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                )
                if resp.status_code == 404:
                    # Some local OpenAI-compat servers omit /models.
                    return True
                return resp.status_code == 200
        except Exception:
            return False


class OfflineProvider(ChatProvider):
    """Fallback when no LLM is available — callers should use retrieve-only mode."""

    name = "offline"

    def __init__(self, model: str = "") -> None:
        self.model = model

    async def complete(
        self,
        system: str,
        messages: list[dict[str, str]],
        *,
        timeout: float = 15.0,
    ) -> str:
        raise RuntimeError("LLM offline — use retrieve-only fallback")

    async def healthy(self, *, timeout: float = 3.0) -> bool:
        return False


def create_chat_provider(
    provider: str,
    *,
    ollama_base_url: str,
    ollama_model: str,
    openai_base_url: str,
    openai_api_key: str,
    openai_model: str,
) -> ChatProvider:
    if provider == "offline":
        return OfflineProvider()
    if provider == "ollama":
        return OllamaProvider(ollama_base_url, ollama_model)
    if provider == "openai_compat":
        return OpenAICompatProvider(openai_base_url, openai_api_key, openai_model)
    raise ValueError(f"Unknown LLM provider: {provider}")
