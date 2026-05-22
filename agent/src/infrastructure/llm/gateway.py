"""Central LLM, embedding, and rerank gateway."""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from typing import Any

import httpx
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_openai import OpenAIEmbeddings

from contracts.llm import (
    ChatModelPolicy,
    EmbeddingModelPolicy,
    ModelCallMetadata,
    ModelUseCase,
    RerankModelPolicy,
)
from infrastructure.llm.clients import create_chat_client, create_embedding_client
from infrastructure.llm.policy import chat_policy, embedding_policy, rerank_policy
from settings.config import Settings, get_settings

logger = logging.getLogger(__name__)


class LlmGateway:
    """Single construction and provider-call boundary for model services."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()

    @property
    def settings(self) -> Settings:
        return self._settings

    def chat_policy(
        self,
        use_case: ModelUseCase,
        *,
        model_name: str | None = None,
        streaming: bool = False,
    ) -> ChatModelPolicy:
        return chat_policy(
            use_case,
            self._settings,
            model_name=model_name,
            streaming=streaming,
        )

    def chat_model(
        self,
        use_case: ModelUseCase,
        *,
        model_name: str | None = None,
        streaming: bool = False,
        token_sink: Callable[[str], None] | None = None,
        callback_factory: Callable[[Callable[[str], None]], BaseCallbackHandler] | None = None,
    ) -> BaseChatModel:
        policy = self.chat_policy(
            use_case,
            model_name=model_name,
            streaming=streaming,
        )
        return create_chat_client(
            policy,
            self._settings,
            token_sink=token_sink,
            callback_factory=callback_factory,
        )

    def embedding_policy(self) -> EmbeddingModelPolicy:
        return embedding_policy(self._settings)

    def embedding_model(self) -> OpenAIEmbeddings:
        return create_embedding_client(self.embedding_policy(), self._settings)

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts:
            return []
        vectors = self.embedding_model().embed_documents(list(texts))
        return [list(vector) for vector in vectors]

    def embed_query(self, query: str) -> list[float]:
        return list(self.embedding_model().embed_query(query))

    def rerank_policy(self) -> RerankModelPolicy:
        return rerank_policy(self._settings)

    def rerank(self, query: str, documents: Sequence[str]) -> list[float]:
        docs = list(documents)
        if not docs:
            return []

        policy = self.rerank_policy()
        payload = {
            "model": policy.model_name,
            "query": query,
            "documents": docs,
            "top_n": len(docs),
        }
        url = f"{self._settings.OPENAI_BASE_URL.rstrip('/')}/rerank"
        try:
            with httpx.Client(timeout=policy.timeout_seconds) as client:
                response = client.post(
                    url,
                    json=payload,
                    headers={"Authorization": f"Bearer {self._settings.OPENAI_API_KEY}"},
                )
                response.raise_for_status()
                body = response.json()
        except (httpx.HTTPError, ValueError):
            logger.debug("rerank API failed; using retrieval order", exc_info=True)
            return fallback_rerank_scores(len(docs))

        return parse_rerank_scores(body, document_count=len(docs))

    def metadata(
        self,
        use_case: ModelUseCase,
        *,
        model_name: str | None = None,
        streaming: bool = False,
    ) -> ModelCallMetadata:
        if use_case is ModelUseCase.EMBEDDING:
            policy = self.embedding_policy()
            return ModelCallMetadata(use_case=use_case, model_name=policy.model_name)
        if use_case is ModelUseCase.RERANK:
            policy = self.rerank_policy()
            return ModelCallMetadata(
                use_case=use_case,
                model_name=policy.model_name,
                timeout_seconds=policy.timeout_seconds,
            )
        policy = self.chat_policy(
            use_case,
            model_name=model_name,
            streaming=streaming,
        )
        return ModelCallMetadata(
            use_case=use_case,
            model_name=policy.model_name,
            timeout_seconds=policy.timeout_seconds,
            max_tokens=policy.max_tokens,
            streaming=policy.streaming,
        )


def fallback_rerank_scores(count: int) -> list[float]:
    """Stable fallback score preserving candidate order."""
    return [float(count - i) for i in range(count)]


def parse_rerank_scores(body: Any, *, document_count: int) -> list[float]:
    """Parse provider rerank response into scores aligned with input documents."""
    results = body.get("results") if isinstance(body, dict) else None
    if not isinstance(results, list):
        return fallback_rerank_scores(document_count)

    scores = [0.0] * document_count
    for item in results:
        if not isinstance(item, dict):
            continue
        index = item.get("index")
        score = item.get("relevance_score", item.get("score"))
        if isinstance(index, int) and 0 <= index < document_count and score is not None:
            scores[index] = float(score)
    if all(score == 0.0 for score in scores):
        return fallback_rerank_scores(document_count)
    return scores


def get_llm_gateway(settings: Settings | None = None) -> LlmGateway:
    """Return a gateway for the current settings context."""
    return LlmGateway(settings=settings)
