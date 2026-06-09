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
    VOLC_ASR_ACCESS_KEY: str | None = Field(
        default=None,
        description=(
            "Volcengine SAUC API key for new console (X-Api-Key header); Back-only secret."
        ),
    )
    VOLC_ASR_APP_KEY: str | None = Field(
        default=None,
        description="Deprecated: legacy X-Api-App-Key; not sent upstream (use VOLC_ASR_ACCESS_KEY).",
    )
    VOLC_ASR_WS_URL: str = Field(
        default="wss://openspeech.bytedance.com/api/v3/sauc/bigmodel",
        description="Volcengine SAUC upstream WebSocket URL.",
    )
    VOLC_ASR_RESOURCE_ID: str = Field(
        default="volc.seedasr.sauc.duration",
        description=(
            "Volcengine SAUC resource id (X-Api-Resource-Id); "
            "ASR 1.0: volc.bigasr.sauc.duration."
        ),
    )
    VOLC_ASR_SEGMENT_MS: int = Field(
        default=200,
        description="PCM segment duration in milliseconds when forwarding to upstream.",
    )
    STT_OPENAI_COMPAT_BASE_URL: str = Field(
        default="https://api.siliconflow.cn/v1",
        description="OpenAI-compatible STT base URL used when VOLC_ASR_ACCESS_KEY is unset.",
    )
    STT_API_KEY: str | None = Field(
        default=None,
        description="Bearer token for OpenAI-compatible audio transcription fallback.",
    )
    SILICONFLOW_STT_API_KEY: str | None = Field(
        default=None,
        description="Alias for STT_API_KEY, matching lcjs env naming.",
    )
    SILICONFLOW_API_KEY: str | None = Field(
        default=None,
        description="Fallback STT key copied from lcjs when STT_API_KEY is unset.",
    )
    SILICONFLOW_STT_MODEL: str = Field(
        default="FunAudioLLM/SenseVoiceSmall",
        description="SiliconFlow audio transcription model for fallback STT.",
    )
    STT_TIMEOUT_SECONDS: float = Field(
        default=60.0,
        description="HTTP timeout for fallback audio transcription requests.",
    )
    XUNFEI_ASR_APP_ID: str | None = Field(
        default=None,
        description="Xunfei streaming ASR AppID; Back-only secret.",
    )
    XUNFEI_ASR_API_KEY: str | None = Field(
        default=None,
        description="Xunfei streaming ASR APIKey; Back-only secret.",
    )
    XUNFEI_ASR_API_SECRET: str | None = Field(
        default=None,
        description="Xunfei streaming ASR APISecret; Back-only secret.",
    )
    XUNFEI_ASR_WS_URL: str = Field(
        default="wss://iat-api.xfyun.cn/v2/iat",
        description="Xunfei voicedictation streaming WebSocket URL.",
    )
    CALL_TRANSCRIPT_SENSITIVE_WORDS: str = Field(
        default="退款,投诉,违约,敏感,辱骂,威胁,诈骗,转账,银行卡,身份证",
        description="Comma-separated keywords to flag in persisted call transcripts.",
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

    def stt_api_key(self) -> str | None:
        for candidate in (
            self.STT_API_KEY,
            self.SILICONFLOW_STT_API_KEY,
            self.SILICONFLOW_API_KEY,
        ):
            if candidate and candidate.strip():
                return candidate.strip()
        return None

    def stt_transcriptions_url(self) -> str:
        return f"{self.STT_OPENAI_COMPAT_BASE_URL.rstrip('/')}/audio/transcriptions"

    def xunfei_asr_configured(self) -> bool:
        return all(
            (
                self.XUNFEI_ASR_APP_ID and self.XUNFEI_ASR_APP_ID.strip(),
                self.XUNFEI_ASR_API_KEY and self.XUNFEI_ASR_API_KEY.strip(),
                self.XUNFEI_ASR_API_SECRET and self.XUNFEI_ASR_API_SECRET.strip(),
            )
        )

    def call_transcript_sensitive_words(self) -> list[str]:
        return [
            word.strip()
            for word in self.CALL_TRANSCRIPT_SENSITIVE_WORDS.split(",")
            if word.strip()
        ]


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
