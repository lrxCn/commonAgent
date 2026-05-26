"""Environment-backed configuration for the Back stub service."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Self

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from settings.database_url import resolve_back_database_url

_settings_override: Settings | None = None

_BACK_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """See back/.env.example for the full contract."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    AGENT_URL: str = Field(
        default="http://127.0.0.1:18080",
        description="Agent Gateway base URL (no trailing slash).",
    )
    INTERNAL_API_KEY: str | None = Field(
        default=None,
        description="Optional key sent as X-Internal-Key when forwarding to Agent.",
    )
    BACK_HOST: str = Field(default="0.0.0.0", description="Uvicorn bind host.")
    BACK_PORT: int = Field(default=8080, description="Uvicorn bind port.")
    DEMO_USER_ID: str = Field(default="demo", description="Stub authenticated user id.")
    DEMO_ROLE_ID: str = Field(default="demo", description="Stub role id for RAG/tools.")
    DEMO_TOOLS_FILE: str = Field(
        default="config/tools.demo.json",
        description="JSON file with demo external tools for this role.",
    )
    AGENT_TIMEOUT_SECONDS: float = Field(
        default=120.0,
        description="HTTP timeout when forwarding chat to Agent.",
    )
    DATABASE_URL: str | None = Field(
        default=None,
        description=(
            "Back business database URL (same Postgres instance as Agent, separate DB). "
            "If omitted, derived from AGENT_DATABASE_URL."
        ),
    )
    AGENT_DATABASE_URL: str | None = Field(
        default=None,
        description=(
            "Agent DATABASE_URL (postgresql://…/common_agent). "
            "Back reuses host/user/password and switches to BACK_DATABASE_NAME."
        ),
    )
    BACK_DATABASE_NAME: str = Field(
        default="common_agent_back",
        description="Database name when deriving DATABASE_URL from AGENT_DATABASE_URL.",
    )
    ADMIN_SEED_PASSWORD: str = Field(
        default="123456",
        description="Default password for seeded admin user (demo only).",
    )
    SESSION_SECRET: str = Field(
        default="change-me-in-production",
        description="Secret for signing HttpOnly session cookies.",
    )
    CORS_ORIGINS: str = Field(
        default="http://127.0.0.1:5173,http://localhost:5173,http://127.0.0.1:3000,http://localhost:3000",
        description="Comma-separated browser origins allowed with credentials.",
    )

    @model_validator(mode="after")
    def resolve_database_url(self) -> Self:
        resolved = resolve_back_database_url(
            database_url=self.DATABASE_URL,
            agent_database_url=self.AGENT_DATABASE_URL,
            back_database_name=self.BACK_DATABASE_NAME,
        )
        object.__setattr__(self, "DATABASE_URL", resolved)
        return self

    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    def resolve_tools_path(self) -> Path:
        path = Path(self.DEMO_TOOLS_FILE)
        if path.is_absolute():
            return path
        return _BACK_ROOT / path


def get_settings() -> Settings:
    if _settings_override is not None:
        return _settings_override
    return _load_settings()


def set_settings_override(settings: Settings | None) -> None:
    global _settings_override
    _settings_override = settings


@lru_cache
def _load_settings() -> Settings:
    return Settings()
