from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    backend_host: str = "127.0.0.1"
    backend_port: int = 8765

    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    codex_binary: str = "codex"
    codex_timeout_seconds: int = 120

    database_url: str = "sqlite:///runtime/hh_copilot.db"
    max_concurrent_ai_jobs: int = Field(default=2, ge=1, le=8)
    max_new_vacancies_per_sync: int = Field(default=30, ge=1, le=500)
    processing_stale_seconds: int = Field(default=600, ge=60)
    max_processing_retries: int = Field(default=2, ge=0, le=10)

    hh_user_agent: str = "HH-Copilot/0.1 (configure-real-contact-email)"
    log_level: str = "INFO"

    @field_validator("backend_host")
    @classmethod
    def loopback_only(cls, value: str) -> str:
        if value not in {"127.0.0.1", "localhost", "::1"}:
            raise ValueError("BACKEND_HOST must be a loopback address")
        return value

    @property
    def resolved_database_url(self) -> str:
        prefix = "sqlite:///"
        if not self.database_url.startswith(prefix):
            return self.database_url
        raw_path = self.database_url.removeprefix(prefix)
        path = Path(raw_path)
        if not path.is_absolute():
            path = PROJECT_ROOT / path
        path.parent.mkdir(parents=True, exist_ok=True)
        return f"sqlite:///{path}"

    @property
    def candidate_profile_path(self) -> Path:
        return PROJECT_ROOT / "data" / "candidate_profile.md"

    @property
    def analysis_prompt_path(self) -> Path:
        return PROJECT_ROOT / "prompts" / "vacancy_analysis.md"

    @property
    def cover_letter_prompt_path(self) -> Path:
        return PROJECT_ROOT / "prompts" / "cover_letter.md"

    @property
    def hh_user_agent_configured(self) -> bool:
        match = re.search(r"[\w.+-]+@([\w.-]+)", self.hh_user_agent)
        if not match:
            return False
        return match.group(1).lower() not in {"example.com", "example.org", "example.net"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
