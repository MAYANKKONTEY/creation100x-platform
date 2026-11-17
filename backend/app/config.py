"""Application settings loaded from environment variables (never hardcoded secrets)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(REPO_ROOT / ".env", ".env"), env_file_encoding="utf-8", extra="ignore"
    )

    app_env: str = "development"
    database_url: str = f"sqlite:///{REPO_ROOT / 'data' / 'growthos.db'}"

    anthropic_api_key: SecretStr | None = None
    claude_model: str = "claude-opus-5-5"
    claude_effort: str = "high"
    claude_server_fallback: bool = True

    openai_api_key: SecretStr | None = None

    # Publishing requires BOTH this env flag and the DB setting to be true.
    publishing_enabled: bool = False

    http_user_agent: str = "LinkedInGrowthOS/0.1 (+research)"
    http_timeout_seconds: float = 20.0
    owner_timezone: str = "UTC"

    config_dir: Path = Field(default=REPO_ROOT / "config")
    skills_dir: Path = Field(default=REPO_ROOT / ".claude" / "skills")
    brand_dir: Path = Field(default=REPO_ROOT / "brand")

    @property
    def llm_configured(self) -> bool:
        return bool(self.anthropic_api_key and self.anthropic_api_key.get_secret_value())


@lru_cache
def get_settings() -> Settings:
    return Settings()
