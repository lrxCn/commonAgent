"""Provider client construction helpers for the LLM gateway."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

from contracts.llm import ChatModelPolicy, EmbeddingModelPolicy
from settings.config import Settings


def create_chat_client(
    policy: ChatModelPolicy,
    settings: Settings,
    *,
    token_sink: Callable[[str], None] | None = None,
    callback_factory: Callable[[Callable[[str], None]], BaseCallbackHandler] | None = None,
) -> BaseChatModel:
    """Create an OpenAI-compatible LangChain chat model from resolved policy."""
    kwargs: dict[str, Any] = {
        "model": policy.model_name,
        "api_key": settings.OPENAI_API_KEY,
        "base_url": settings.OPENAI_BASE_URL,
        "temperature": policy.temperature,
    }
    if policy.max_tokens is not None:
        kwargs["max_completion_tokens"] = policy.max_tokens
    if policy.timeout_seconds is not None:
        kwargs["timeout"] = policy.timeout_seconds
    if policy.max_retries is not None:
        kwargs["max_retries"] = policy.max_retries
    if policy.streaming:
        kwargs["streaming"] = True
        if token_sink is not None and callback_factory is not None:
            kwargs["callbacks"] = [callback_factory(token_sink)]
    return ChatOpenAI(**kwargs)


def create_embedding_client(
    policy: EmbeddingModelPolicy,
    settings: Settings,
) -> OpenAIEmbeddings:
    """Create an OpenAI-compatible embedding client from resolved policy."""
    # EMBEDDING_MODEL_DIMS is the Qdrant/Store vector contract. Some
    # OpenAI-compatible providers (SiliconFlow bge models) reject the optional
    # `dimensions` request parameter, so do not send it to the provider.
    # Disable LangChain's token-length-safe path as well; it can send token id
    # arrays that these providers reject even though plain string input works.
    return OpenAIEmbeddings(
        model=policy.model_name,
        api_key=settings.OPENAI_API_KEY,
        base_url=settings.OPENAI_BASE_URL,
        check_embedding_ctx_length=False,
    )
