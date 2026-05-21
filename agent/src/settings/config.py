"""Pydantic Settings mapping for agent/.env contract (see .env.example)."""

from __future__ import annotations

from functools import lru_cache
from typing import Self

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_settings_override: Settings | None = None


class Settings(BaseSettings):
    """Environment-backed configuration aligned with agent/.env.example and agent/.env."""

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
    LANGCHAIN_TRACE_MESSAGE_MAX_CHARS: int = Field(
        default=500,
        description="Maximum characters kept for message previews in trace metadata.",
    )

    # --- LLM provider (SiliconFlow, OpenAI-compatible) ---
    OPENAI_API_KEY: str = Field(
        ...,
        description="API key for LLM calls via OPENAI_BASE_URL (e.g. SiliconFlow).",
    )
    OPENAI_BASE_URL: str = Field(
        default="https://api.siliconflow.cn/v1",
        description="OpenAI-compatible base URL for chat completions.",
    )
    OPENAI_MODEL_NAME: str = Field(
        default="Pro/moonshotai/Kimi-K2.6",
        description="Default chat model identifier on the provider.",
    )

    # --- Query rewrite ---
    REWRITE_MODEL_NAME: str | None = Field(
        default=None,
        description="Chat model for query rewrite; defaults to OPENAI_MODEL_NAME when unset.",
    )
    REWRITE_MAX_TOKENS: int = Field(
        default=64,
        description="Maximum completion tokens for query rewrite calls.",
    )
    REWRITE_TIMEOUT_SECONDS: float = Field(
        default=15,
        description="Timeout in seconds for query rewrite calls.",
    )
    REWRITE_SKIP_ENABLED: bool = Field(
        default=True,
        description="When true, skip rewrite LLM for chitchat/standalone/self-contained turns.",
    )
    REWRITE_MIN_SELF_CONTAINED_LEN: int = Field(
        default=8,
        description="Minimum user message length for standalone/self-contained rewrite skip rules.",
    )
    REWRITE_FORCE: bool = Field(
        default=False,
        description="Debug: always invoke rewrite LLM even when skip rules would apply.",
    )

    # --- Chitchat lightweight executor ---
    CHITCHAT_USE_LLM: bool = Field(
        default=False,
        description="When true, chitchat uses a small LLM instead of template replies.",
    )
    CHITCHAT_MODEL_NAME: str | None = Field(
        default=None,
        description="Chat model for chitchat; defaults to OPENAI_MODEL_NAME when unset.",
    )
    CHITCHAT_MAX_TOKENS: int = Field(
        default=48,
        description="Maximum completion tokens for chitchat small-model calls.",
    )
    CHITCHAT_TIMEOUT_SECONDS: float = Field(
        default=5,
        description="Timeout in seconds for chitchat small-model calls.",
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
    RAG_ROUTER_MAX_TOKENS: int = Field(
        default=32,
        description="Maximum completion tokens for hybrid RAG router classification.",
    )
    RAG_ROUTER_TIMEOUT_SECONDS: float = Field(
        default=5,
        description="Timeout in seconds for hybrid RAG router classification.",
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

    # --- RagSubAgent second retrieval ---
    RAG_SUBAGENT_SCORE_THRESHOLD: float = Field(
        default=0.3,
        description="Delegate RagSubAgent when primary max chunk score is below this.",
    )
    RAG_SUBAGENT_TOP_K: int | None = Field(
        default=None,
        description="Second-pass retrieval top_k; defaults to 2× RERANK_TOP_K when unset.",
    )
    RAG_CHUNKS_MAX: int = Field(
        default=10,
        description="Maximum merged rag_chunks after primary + RagSubAgent passes.",
    )

    # --- KB ingest ---
    CHUNK_SIZE_TOKENS: int = Field(
        default=768,
        description="Target chunk size in estimated tokens (README target: 512–1024).",
    )
    CHUNK_OVERLAP_RATIO: float = Field(
        default=0.12,
        description="Chunk overlap ratio (README target: 10–15%).",
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
        default=False,
        description="When true, skip live Qdrant retrieval and return fixture chunks.",
    )

    # --- mem0 (local OSS + Qdrant; do not use MEM0_API_KEY / MemoryClient) ---
    MEM0_MOCK: bool = Field(
        default=False,
        description="When true, skip mem0/Qdrant reads and return an empty memory list.",
    )
    MEM0_READ_LIMIT: int = Field(
        default=50,
        description="Maximum number of mem0 facts to fetch per user via get_all top_k.",
    )
    MEM0_LLM_MODEL_NAME: str | None = Field(
        default=None,
        description="Dedicated small model for mem0 infer writes; required to avoid falling back to OPENAI_MODEL_NAME.",
    )
    MEM0_LLM_MAX_TOKENS: int = Field(
        default=128,
        description="Maximum completion tokens for mem0 infer extraction calls.",
    )
    MEM0_LLM_TIMEOUT_SECONDS: float = Field(
        default=10,
        description="Timeout in seconds for mem0 infer extraction calls.",
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

    # --- Context assembly ---
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
    MEMORY_PROFILE_MAX_FACTS: int = Field(
        default=6,
        description="Maximum normalized memory_profile facts injected into the system prompt.",
    )
    MEM0_FREE_TEXT_MAX_FACTS: int = Field(
        default=10,
        description="Maximum uncategorized mem0 facts injected into the system prompt.",
    )
    SUMMARY_MAX_CHARS: int = Field(
        default=4000,
        description="Maximum rolling-summary characters injected into the system prompt.",
    )
    RAG_CHUNK_MAX_CHARS: int = Field(
        default=1200,
        description="Maximum characters kept per RAG chunk in the system prompt.",
    )
    RAG_CONTEXT_MAX_CHARS: int = Field(
        default=6000,
        description="Maximum formatted RAG excerpt block characters in the system prompt.",
    )
    TOOLS_SCHEMA_MAX_CHARS: int = Field(
        default=3000,
        description="Maximum formatted external client tool schema characters per turn.",
    )
    MODEL_MESSAGE_MAX_TURNS: int = Field(
        default=24,
        description="Maximum historical conversation turns sent to the main model.",
    )
    MODEL_MESSAGE_MAX_CHARS: int = Field(
        default=20000,
        description="Maximum total message-content characters sent to the main model.",
    )

    @field_validator(
        "LANGCHAIN_TRACING_V2",
        "REWRITE_SKIP_ENABLED",
        "REWRITE_FORCE",
        "GUARDRAILS_ENABLED",
        "MEM0_MOCK",
        "QDRANT_MOCK",
        "CHITCHAT_USE_LLM",
        mode="before",
    )
    @classmethod
    def _parse_bool_flag(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "on"}
        return value

    @field_validator(
        "LANGCHAIN_API_KEY",
        "REWRITE_MODEL_NAME",
        "CHITCHAT_MODEL_NAME",
        "RAG_ROUTER_MODEL_NAME",
        "MEM0_LLM_MODEL_NAME",
        "RAG_SUBAGENT_TOP_K",
        mode="before",
    )
    @classmethod
    def _empty_string_as_none(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
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
