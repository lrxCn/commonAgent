"""Pydantic Settings mapping for agent/.env contract (see .env.example)."""

from __future__ import annotations

from functools import lru_cache
from typing import Self

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_settings_override: Settings | None = None


class Settings(BaseSettings):
    """Environment-backed configuration aligned with agent/.env.example."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # --- LangSmith ---
    LANGSMITH_API_KEY: str = Field(
        ...,
        description="LangSmith API key (Smith console); used when LANGCHAIN_API_KEY is unset.",
    )
    LANGCHAIN_TRACING_V2: bool = Field(
        default=True,
        description="Enable LangSmith / LangChain tracing when true.",
    )
    LANGCHAIN_PROJECT: str = Field(
        default="common-agent",
        description="LangSmith project name for trace grouping.",
    )
    LANGCHAIN_ENDPOINT: str = Field(
        default="https://api.smith.langchain.com",
        description="LangSmith API endpoint URL.",
    )
    LANGCHAIN_API_KEY: str | None = Field(
        default=None,
        description="Optional LangChain API key; falls back to LANGSMITH_API_KEY if omitted.",
    )

    # --- LLM (SiliconFlow, OpenAI-compatible) ---
    OPENAI_API_KEY: str = Field(
        ...,
        description="API key for LLM calls via OPENAI_BASE_URL (e.g. SiliconFlow).",
    )
    OPENAI_BASE_URL: str = Field(
        default="https://api.siliconflow.cn/v1",
        description="OpenAI-compatible base URL for chat completions.",
    )
    OPENAI_MODEL_NAME: str = Field(
        default="Pro/deepseek-ai/DeepSeek-V3.2",
        description="Default chat model identifier on the provider.",
    )
    REWRITE_MODEL_NAME: str | None = Field(
        default=None,
        description="Chat model for query rewrite; defaults to OPENAI_MODEL_NAME when unset.",
    )

    # --- RAG router ---
    RAG_ROUTER_MODE: str = Field(
        default="hybrid",
        description="RAG routing: rules-only or rules + LLM for uncertain cases.",
    )
    RAG_ROUTER_MODEL_NAME: str | None = Field(
        default=None,
        description="Chat model for hybrid RAG router; defaults to OPENAI_MODEL_NAME when unset.",
    )

    # --- Embedding ---
    EMBEDDING_MODEL: str = Field(
        default="BAAI/bge-large-zh-v1.5",
        description="Embedding model id for vectorization.",
    )
    EMBEDDING_MODEL_DIMS: int = Field(
        default=1024,
        description="Embedding vector dimension; must match Qdrant collection size.",
    )

    # --- Rerank ---
    RERANK_MODEL: str = Field(
        default="BAAI/bge-reranker-v2-m3",
        description="Rerank model id for candidate reordering.",
    )
    RERANK_TOP_K: int = Field(
        default=10,
        description="Maximum number of candidates sent to the reranker.",
    )

    # --- Qdrant ---
    QDRANT_HOST: str = Field(
        default="localhost",
        description="Qdrant server hostname.",
    )
    QDRANT_PORT: int = Field(
        default=6333,
        description="Qdrant HTTP port.",
    )
    QDRANT_COLLECTION_KB: str = Field(
        default="common_agent_kb",
        description="Qdrant collection name for knowledge-base vectors.",
    )
    QDRANT_COLLECTION_MEM0: str = Field(
        default="common_agent_mem0",
        description="Qdrant collection for mem0 user-preference vectors (separate from KB).",
    )
    QDRANT_MOCK: bool = Field(
        default=True,
        description="When true, skip live Qdrant retrieval and return fixture chunks.",
    )

    # --- mem0 (local OSS + Qdrant; do not use MEM0_API_KEY / MemoryClient) ---
    MEM0_MOCK: bool = Field(
        default=True,
        description="When true, skip mem0/Qdrant reads and return an empty memory list.",
    )
    MEM0_READ_LIMIT: int = Field(
        default=50,
        description="Maximum number of mem0 facts to fetch per user via get_all top_k.",
    )

    # --- Postgres ---
    DATABASE_URL: str = Field(
        ...,
        description="PostgreSQL URL for LangGraph checkpointer (asyncpg-compatible).",
    )

    # --- Gateway ---
    AGENT_HOST: str = Field(
        default="0.0.0.0",
        description="HTTP bind host for the agent gateway.",
    )
    AGENT_PORT: int = Field(
        default=18080,
        description="HTTP bind port for the agent gateway.",
    )

    # --- Guardrails ---
    GUARDRAILS_ENABLED: bool = Field(
        default=True,
        description="When false, inbound/outbound text guardrails are skipped.",
    )

    # --- Context assembly (code defaults only; not in .env contract) ---
    CONTEXT_PREFIX_TURNS: int = Field(
        default=4,
        description="First K conversation turns in model messages (prefix).",
    )
    CONTEXT_RECENT_TURNS: int = Field(
        default=20,
        description="Last M conversation turns in model messages (recent window).",
    )
    CONTEXT_ORIGINAL_HUMAN_METADATA_KEY: str = Field(
        default="original_human_content",
        description="HumanMessage metadata key for pre-rewrite user text.",
    )

    @field_validator(
        "LANGCHAIN_TRACING_V2",
        "GUARDRAILS_ENABLED",
        "MEM0_MOCK",
        "QDRANT_MOCK",
        mode="before",
    )
    @classmethod
    def _parse_bool_flag(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "on"}
        return value

    @field_validator("RAG_ROUTER_MODE", mode="before")
    @classmethod
    def _normalize_rag_router_mode(cls, value: object) -> str:
        if value is None:
            return "hybrid"
        mode = str(value).strip().lower()
        if mode not in {"rules", "hybrid"}:
            msg = "RAG_ROUTER_MODE must be 'rules' or 'hybrid'"
            raise ValueError(msg)
        return mode

    @model_validator(mode="after")
    def _apply_langchain_api_key_fallback(self) -> Self:
        if not self.LANGCHAIN_API_KEY:
            object.__setattr__(self, "LANGCHAIN_API_KEY", self.LANGSMITH_API_KEY)
        return self

    @property
    def qdrant_url(self) -> str:
        """HTTP URL for Qdrant client connections."""
        return f"http://{self.QDRANT_HOST}:{self.QDRANT_PORT}"


@lru_cache
def _load_settings() -> Settings:
    return Settings()


def get_settings() -> Settings:
    """Return cached settings; use set_settings_override in tests."""
    if _settings_override is not None:
        return _settings_override
    return _load_settings()


def set_settings_override(settings: Settings | None) -> None:
    """Replace settings for tests; pass None to clear."""
    global _settings_override
    _settings_override = settings


def reset_settings() -> None:
    """Clear override and reload cache (e.g. between tests)."""
    set_settings_override(None)
    _load_settings.cache_clear()
