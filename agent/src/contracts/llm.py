"""Typed contracts for provider model usage."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ModelUseCase(StrEnum):
    """Logical model purposes used by the infrastructure LLM gateway."""

    MAIN_ANSWER = "main_answer"
    RAG_ANSWER = "rag_answer"
    REWRITE = "rewrite"
    ROUTER = "router"
    CHITCHAT = "chitchat"
    MEMORY_EXTRACT = "memory_extract"
    MEM0_WRITE = "mem0_write"  # deprecated alias; removed in task 74
    INTENT_CLASSIFIER = "intent_classifier"
    EMBEDDING = "embedding"
    RERANK = "rerank"
    SUMMARY = "summary"


@dataclass(frozen=True)
class ModelCallMetadata:
    """Resolved provider call attributes for tracing and tests."""

    use_case: ModelUseCase
    model_name: str
    timeout_seconds: float | None = None
    max_tokens: int | None = None
    streaming: bool = False
    fallback: bool = False
    fallback_reason: str = ""


@dataclass(frozen=True)
class ChatModelPolicy:
    """Chat model construction policy resolved from settings."""

    use_case: ModelUseCase
    model_name: str
    temperature: float
    max_tokens: int | None = None
    timeout_seconds: float | None = None
    max_retries: int | None = None
    streaming: bool = False


@dataclass(frozen=True)
class EmbeddingModelPolicy:
    """Embedding model construction policy resolved from settings."""

    use_case: ModelUseCase
    model_name: str
    dimensions: int


@dataclass(frozen=True)
class RerankModelPolicy:
    """Rerank provider policy resolved from settings."""

    use_case: ModelUseCase
    model_name: str
    timeout_seconds: float
