"""Application settings loaded from environment / .env."""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

INSECURE_API_TOKENS = frozenset({"", "change-me"})
LOOPBACK_BIND_HOSTS = frozenset({"127.0.0.1", "::1", "localhost"})
LOOPBACK_CLIENT_HOSTS = LOOPBACK_BIND_HOSTS | {"testclient"}


def resolve_env_file(*, start: Path | None = None) -> Path | None:
    """Find `.env`: cwd first, then parents (repo root when run from apps/core)."""
    here = (start or Path.cwd()).resolve()
    for base in (here, *here.parents):
        candidate = base / ".env"
        if candidate.is_file():
            return candidate
    return None


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
        # Prefer get_settings() which re-resolves; this covers direct Settings().
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

    # Voice STT (ADR-08): auto uses OpenAI Whisper only when OPENAI_API_KEY is set.
    juno_voice_backend: str = "auto"  # auto | openai | stub | off
    openai_whisper_model: str = "whisper-1"

    # M4 jobs (ADR-07): AsyncIOScheduler on the shared serve loop.
    juno_jobs_enabled: bool = True
    juno_jobs_timezone: str = "UTC"
    juno_jobs_smoke: bool = False
    juno_jobs_digest_daily: bool = True
    juno_jobs_digest_daily_cron: str = "0 7 * * *"
    juno_jobs_digest_weekly: bool = True
    juno_jobs_digest_weekly_cron: str = "0 7 * * mon"
    juno_jobs_resurfacing: bool = True
    juno_jobs_resurfacing_cron: str = "0 * * * *"
    juno_jobs_polish: bool = True
    juno_jobs_polish_cron: str = "0 8 * * *"

    # M5 drafts (ADR-09): template HITL artifacts; never auto-publish.
    juno_drafts_smoke: bool = False
    juno_drafts_generator: str = "template"  # template (llm deferred to #109)

    # M5 Slack (PRD §6.3): opt-in URL/doc forward into inbox space — not a workspace bot.
    juno_slack_forward: bool = False

    # M5 prune (ADR-12): unused captures older than this many days are HITL candidates.
    juno_prune_min_age_days: int = 90

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
    """Load settings from the environment and the nearest `.env` (cwd or parents)."""
    env_file = resolve_env_file()
    if env_file is not None:
        return Settings(_env_file=env_file)
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
