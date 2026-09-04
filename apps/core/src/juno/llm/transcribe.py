"""Voice memo transcription. Audio is not stored; only the transcript is ingested."""

from __future__ import annotations

import logging
from typing import Any, Protocol

import httpx

logger = logging.getLogger("juno.llm")


class Transcriber(Protocol):
    name: str

    async def transcribe(self, audio: bytes, *, filename: str = "voice.ogg") -> str: ...

    async def healthy(self, *, timeout: float = 3.0) -> bool: ...


class OfflineTranscriber:
    """No network STT. Operator must set OPENAI_API_KEY or JUNO_VOICE_BACKEND=openai."""

    name = "offline"

    async def transcribe(self, audio: bytes, *, filename: str = "voice.ogg") -> str:
        raise RuntimeError(
            "Voice transcription is off. Set JUNO_VOICE_BACKEND=openai and OPENAI_API_KEY "
            "(audio is sent to that API), or use JUNO_VOICE_BACKEND=stub in tests."
        )

    async def healthy(self, *, timeout: float = 3.0) -> bool:
        return False


class StubTranscriber:
    name = "stub"

    def __init__(self, text: str = "stub voice transcript") -> None:
        self.text = text

    async def transcribe(self, audio: bytes, *, filename: str = "voice.ogg") -> str:
        return self.text

    async def healthy(self, *, timeout: float = 3.0) -> bool:
        return True


class OpenAIWhisperTranscriber:
    name = "openai_whisper"

    def __init__(self, base_url: str, api_key: str, model: str = "whisper-1") -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model

    async def transcribe(self, audio: bytes, *, filename: str = "voice.ogg") -> str:
        if not audio:
            raise RuntimeError("empty voice note")
        headers = {"Authorization": f"Bearer {self.api_key}"}
        files = {"file": (filename, audio, "application/octet-stream")}
        data = {"model": self.model}
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{self.base_url}/audio/transcriptions",
                headers=headers,
                files=files,
                data=data,
            )
            resp.raise_for_status()
            payload: dict[str, Any] = resp.json()
            text = str(payload.get("text") or "").strip()
            if not text:
                raise RuntimeError("whisper returned empty transcript")
            return text

    async def healthy(self, *, timeout: float = 3.0) -> bool:
        return bool(self.api_key)


def create_transcriber(
    backend: str,
    *,
    openai_api_key: str = "",
    openai_base_url: str = "https://api.openai.com/v1",
    openai_whisper_model: str = "whisper-1",
) -> Transcriber:
    choice = (backend or "auto").strip().lower()
    if choice == "stub":
        return StubTranscriber()
    if choice == "off" or choice == "offline":
        return OfflineTranscriber()
    if choice == "openai" or (choice == "auto" and openai_api_key.strip()):
        if not openai_api_key.strip():
            return OfflineTranscriber()
        return OpenAIWhisperTranscriber(
            openai_base_url, openai_api_key.strip(), model=openai_whisper_model
        )
    return OfflineTranscriber()
