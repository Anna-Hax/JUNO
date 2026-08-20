"""Application settings loaded from environment / .env."""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    telegram_bot_token: str = ""
    allowed_telegram_user_ids: str = ""

    juno_data_dir: Path = Path("./data")
    juno_inbox_dir: Path = Path("./inbox")

    juno_api_host: str = "127.0.0.1"
    juno_api_port: int = 8787
    juno_api_token: str = "change-me"

    llm_provider: str = "ollama"  # ollama | openai_compat
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "llama3.2"
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4o-mini"

    embedding_model: str = "all-MiniLM-L6-v2"
    embedding_backend: str = "sentence_transformers"  # stub | sentence_transformers

    def allowed_user_id_set(self) -> set[int]:
        if not self.allowed_telegram_user_ids.strip():
            return set()
        return {int(x.strip()) for x in self.allowed_telegram_user_ids.split(",") if x.strip()}

    @property
    def sqlite_path(self) -> Path:
        return self.juno_data_dir / "juno.db"

    @property
    def chroma_path(self) -> Path:
        return self.juno_data_dir / "chroma"


def get_settings() -> Settings:
    return Settings()
