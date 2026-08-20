"""Chat LLM providers with health probes."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

import httpx


class ChatProvider(ABC):
    name: str

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
    async def healthy(self) -> bool:
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

    async def healthy(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                resp = await client.get(f"{self.base_url}/api/tags")
                return resp.status_code == 200
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

    async def healthy(self) -> bool:
        return bool(self.api_key)


class OfflineProvider(ChatProvider):
    """Fallback when no LLM is available — callers should use retrieve-only mode."""

    name = "offline"

    async def complete(
        self,
        system: str,
        messages: list[dict[str, str]],
        *,
        timeout: float = 15.0,
    ) -> str:
        raise RuntimeError("LLM offline — use retrieve-only fallback")

    async def healthy(self) -> bool:
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
    if provider == "ollama":
        return OllamaProvider(ollama_base_url, ollama_model)
    if provider == "openai_compat":
        return OpenAICompatProvider(openai_base_url, openai_api_key, openai_model)
    raise ValueError(f"Unknown LLM provider: {provider}")
