"""Application settings loaded from environment / .env."""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

INSECURE_API_TOKENS = frozenset({"", "change-me"})
LOOPBACK_BIND_HOSTS = frozenset({"127.0.0.1", "::1", "localhost"})
LOOPBACK_CLIENT_HOSTS = LOOPBACK_BIND_HOSTS | {"testclient"}


def api_token_is_configured(token: str | None) -> bool:
    """True when JUNO_API_TOKEN is set to something other than the example default."""
    return (token or "").strip().lower() not in INSECURE_API_TOKENS


def is_loopback_bind_host(host: str | None) -> bool:
    return (host or "").strip().lower() in LOOPBACK_BIND_HOSTS


def is_loopback_client_host(host: str | None) -> bool:
    h = (host or "").strip().lower()
    if h in LOOPBACK_CLIENT_HOSTS:
        return True
    if h.startswith("::ffff:"):
        return h[7:] == "127.0.0.1"
    return False


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

    llm_provider: str = "ollama"  # ollama | openai_compat | offline
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

    @property
    def llm_model(self) -> str:
        if self.llm_provider == "openai_compat":
            return self.openai_model
        if self.llm_provider == "offline":
            return ""
        return self.ollama_model


def get_settings() -> Settings:
    return Settings()


def validate_serve_settings(settings: Settings) -> None:
    """Refuse to listen if the API would be misconfigured for a local-first agent."""
    if not api_token_is_configured(settings.juno_api_token):
        raise ValueError(
            "JUNO_API_TOKEN is unset or still 'change-me'. Set a secret in .env before serving."
        )
    if not is_loopback_bind_host(settings.juno_api_host):
        raise ValueError(
            "JUNO_API_HOST must be loopback (127.0.0.1 / ::1 / localhost), "
            f"got {settings.juno_api_host!r}"
        )
