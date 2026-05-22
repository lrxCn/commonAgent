"""RAG retrieval orchestration over replaceable stores and rerankers."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any, Protocol

from contracts.rag import RagChunk, RagResult
from domain.rag.merge import merge_candidates
from domain.rag.models import RagCandidate, RagQueryPlan
from observability.tracing import attach_run_metadata
from settings.config import Settings

logger = logging.getLogger(__name__)


class RagStore(Protocol):
    """Role-aware KB store adapter."""

    def dense_search(
        self,
        *,
        role_id: str,
        query_vector: list[float],
        limit: int,
    ) -> list[RagCandidate]: ...

    def lexical_search(
        self,
        *,
        role_id: str,
        query: str,
        limit: int,
    ) -> list[RagCandidate]: ...


RerankFn = Callable[[str, list[str]], list[float]]
EmbedQueryFn = Callable[[str, Settings], list[float]]


def build_retrieval_metadata(
    *,
    role_id: str,
    query: str,
    dense_count: int,
    sparse_count: int,
    result_count: int,
    mock: bool,
    second_pass: bool = False,
) -> dict[str, Any]:
    """Span metadata for LangSmith."""
    return {
        "rag.role_id": role_id,
        "rag.query_len": len(query),
        "rag.dense_hits": dense_count,
        "rag.sparse_hits": sparse_count,
        "rag.result_count": result_count,
        "rag.mock": mock,
        "rag.second_pass": second_pass,
    }


class RagRetrievalService:
    """Hybrid retrieval service with explicit store, embedding, and rerank dependencies."""

    def __init__(
        self,
        *,
        store: RagStore,
        embed_query: EmbedQueryFn,
        rerank: Callable[[str, list[RagCandidate], int, Settings], list[RagChunk]],
        settings: Settings,
    ) -> None:
        self._store = store
        self._embed_query = embed_query
        self._rerank = rerank
        self._settings = settings

    def retrieve(self, plan: RagQueryPlan) -> RagResult:
        """Execute dense + lexical retrieval and final rerank."""
        dense_hits: list[RagCandidate] = []
        try:
            dense_vector = self._embed_query(plan.query, self._settings)
        except Exception:
            logger.debug("query embedding failed; continuing with BM25 fallback", exc_info=True)
        else:
            dense_hits = self._store.dense_search(
                role_id=plan.role_id,
                query_vector=dense_vector,
                limit=plan.prefetch_limit,
            )

        sparse_hits = self._store.lexical_search(
            role_id=plan.role_id,
            query=plan.query,
            limit=plan.prefetch_limit,
        )
        merged = merge_candidates(dense_hits, sparse_hits)
        chunks = self._rerank(plan.query, merged, plan.top_k, self._settings)

        metadata = build_retrieval_metadata(
            role_id=plan.role_id,
            query=plan.query,
            dense_count=len(dense_hits),
            sparse_count=len(sparse_hits),
            result_count=len(chunks),
            mock=False,
            second_pass=plan.second_pass,
        )
        attach_run_metadata(metadata)
        return RagResult.from_chunks(
            chunks,
            query=plan.query,
            role_id=plan.role_id,
            second_pass=plan.second_pass,
            dense_count=len(dense_hits),
            sparse_count=len(sparse_hits),
            reranked_count=len(chunks),
            mock=False,
        )
