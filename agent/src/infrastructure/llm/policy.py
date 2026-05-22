"""Model policy resolution for every provider use case."""

from __future__ import annotations

from contracts.llm import (
    ChatModelPolicy,
    EmbeddingModelPolicy,
    ModelUseCase,
    RerankModelPolicy,
)
from settings.config import Settings


def _clean_model(value: str | None, fallback: str) -> str:
    return (value or fallback).strip()


def chat_policy(
    use_case: ModelUseCase,
    settings: Settings,
    *,
    model_name: str | None = None,
    streaming: bool = False,
) -> ChatModelPolicy:
    """Resolve chat model settings for one logical use case."""
    if use_case is ModelUseCase.REWRITE:
        return ChatModelPolicy(
            use_case=use_case,
            model_name=_clean_model(model_name or settings.REWRITE_MODEL_NAME, settings.OPENAI_MODEL_NAME),
            temperature=0,
            max_tokens=settings.REWRITE_MAX_TOKENS,
            timeout_seconds=settings.REWRITE_TIMEOUT_SECONDS,
            max_retries=0,
            streaming=streaming,
        )
    if use_case is ModelUseCase.ROUTER:
        return ChatModelPolicy(
            use_case=use_case,
            model_name=_clean_model(model_name or settings.RAG_ROUTER_MODEL_NAME, settings.OPENAI_MODEL_NAME),
            temperature=0,
            max_tokens=settings.RAG_ROUTER_MAX_TOKENS,
            timeout_seconds=settings.RAG_ROUTER_TIMEOUT_SECONDS,
            max_retries=0,
            streaming=streaming,
        )
    if use_case is ModelUseCase.CHITCHAT:
        return ChatModelPolicy(
            use_case=use_case,
            model_name=_clean_model(model_name or settings.CHITCHAT_MODEL_NAME, settings.OPENAI_MODEL_NAME),
            temperature=0.2,
            max_tokens=settings.CHITCHAT_MAX_TOKENS,
            timeout_seconds=settings.CHITCHAT_TIMEOUT_SECONDS,
            max_retries=0,
            streaming=streaming,
        )
    if use_case is ModelUseCase.MEM0_WRITE:
        return ChatModelPolicy(
            use_case=use_case,
            model_name=_clean_model(model_name or settings.MEM0_LLM_MODEL_NAME, settings.OPENAI_MODEL_NAME),
            temperature=0.1,
            max_tokens=settings.MEM0_LLM_MAX_TOKENS,
            timeout_seconds=settings.MEM0_LLM_TIMEOUT_SECONDS,
            max_retries=0,
            streaming=streaming,
        )
    if use_case is ModelUseCase.SUMMARY:
        return ChatModelPolicy(
            use_case=use_case,
            model_name=_clean_model(model_name, settings.OPENAI_MODEL_NAME),
            temperature=0.2,
            streaming=streaming,
        )
    if use_case in {ModelUseCase.MAIN_ANSWER, ModelUseCase.RAG_ANSWER}:
        return ChatModelPolicy(
            use_case=use_case,
            model_name=_clean_model(model_name, settings.OPENAI_MODEL_NAME),
            temperature=0.2,
            streaming=streaming,
        )
    msg = f"{use_case.value} is not a chat model use case"
    raise ValueError(msg)


def embedding_policy(settings: Settings) -> EmbeddingModelPolicy:
    """Resolve embedding model settings."""
    return EmbeddingModelPolicy(
        use_case=ModelUseCase.EMBEDDING,
        model_name=settings.EMBEDDING_MODEL,
        dimensions=settings.EMBEDDING_MODEL_DIMS,
    )


def rerank_policy(settings: Settings) -> RerankModelPolicy:
    """Resolve rerank model settings."""
    return RerankModelPolicy(
        use_case=ModelUseCase.RERANK,
        model_name=settings.RERANK_MODEL,
        timeout_seconds=30,
    )
