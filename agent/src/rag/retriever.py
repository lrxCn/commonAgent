"""RAG retrieval compatibility facade over domain and infrastructure services."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any, TypedDict

from qdrant_client import QdrantClient

from contracts.events import ObservabilityEventType
from contracts.rag import RagChunk
from domain.rag.formatting import format_rag_chunks_for_system, rag_chunk_to_dict
from domain.rag.lexical.tokenizer import lexical_terms as _lexical_terms
from domain.rag.merge import merge_candidates
from domain.rag.models import RagCandidate, RagQueryPlan
from domain.rag.service import RagRetrievalService, build_retrieval_metadata
from infrastructure.llm.gateway import get_llm_gateway
from infrastructure.llm.rerank_client import default_rerank
from infrastructure.qdrant.kb_store import DENSE_VECTOR_NAME, QdrantKbStore, get_qdrant_client
from infrastructure.qdrant.kb_store import role_filter as _role_filter
from infrastructure.qdrant.kb_store import roles_filter as _roles_filter
from infrastructure.qdrant.kb_store import set_qdrant_client_override
from infrastructure.qdrant.payload import (
    hit_to_candidate as _hit_to_candidate,
    payload_text as _payload_text,
    point_to_candidate as _point_to_candidate,
)
from observability.tracing import emit_event, rerank_traceable, retrieve_traceable
from settings.config import Settings, get_settings

_DENSE_VECTOR_NAME = DENSE_VECTOR_NAME

__all__ = [
    "RagChunk",
    "RagRetrievalNodeState",
    "_DENSE_VECTOR_NAME",
    "_bm25_search",
    "_dense_search",
    "_get_qdrant_client",
    "_hit_to_candidate",
    "_lexical_terms",
    "_merge_candidates",
    "_payload_text",
    "_point_to_candidate",
    "_role_filter",
    "_roles_filter",
    "_sparse_search",
    "_text_search",
    "build_retrieval_metadata",
    "default_rerank",
    "format_rag_chunks_for_system",
    "rag_chunk_to_dict",
    "rag_retrieval_node",
    "rerank_candidates",
    "reset_retriever_overrides",
    "retrieve",
    "set_embed_query",
    "set_qdrant_client",
    "set_reranker",
]

RerankFn = Callable[[str, list[str]], list[float]]

_qdrant_client_override: QdrantClient | None = None
_reranker_override: RerankFn | None = None
_embed_query_override: Callable[[str], list[float]] | None = None


class RagRetrievalNodeState(TypedDict, total=False):
    """Minimal state slice for rag_retrieval_node."""

    role_ids: list[str]
    rewritten_query: str
    rag_skipped: bool
    rag_chunks: list[RagChunk]


_MOCK_CHUNKS: tuple[RagChunk, ...] = (
    RagChunk(
        doc_id="doc-reimbursement",
        chunk_id="chunk-001",
        text="报销制度：差旅费需在出差结束后 30 日内提交审批。",
        score=0.92,
        channel="mock",
    ),
    RagChunk(
        doc_id="doc-reimbursement",
        chunk_id="chunk-002",
        text="报销制度：单笔超过 5000 元需部门负责人加签。",
        score=0.88,
        channel="mock",
    ),
    RagChunk(
        doc_id="doc-leave",
        chunk_id="chunk-010",
        text="年假规则：工作满一年享有 5 天带薪年假。",
        score=0.85,
        channel="mock",
    ),
)

_MOCK_ROLE_BY_DOC: dict[str, str] = {
    "doc-reimbursement": "role-sales",
    "doc-leave": "role-hr",
}


def set_qdrant_client(client: QdrantClient | None) -> None:
    """Replace Qdrant client (tests). Pass None to clear."""
    global _qdrant_client_override
    _qdrant_client_override = client
    set_qdrant_client_override(client)


def set_reranker(reranker: RerankFn | None) -> None:
    """Replace rerank implementation (tests). Pass None to clear."""
    global _reranker_override
    _reranker_override = reranker


def set_embed_query(fn: Callable[[str], list[float]] | None) -> None:
    """Replace query embedding (tests). Pass None to clear."""
    global _embed_query_override
    _embed_query_override = fn


def reset_retriever_overrides() -> None:
    """Clear all test overrides."""
    set_qdrant_client(None)
    set_reranker(None)
    set_embed_query(None)


def _text(value: str | None) -> str:
    return (value or "").strip()


def _get_qdrant_client(settings: Settings) -> QdrantClient:
    if _qdrant_client_override is not None:
        return _qdrant_client_override
    return get_qdrant_client(settings)


def _embed_query(query: str, settings: Settings) -> list[float]:
    if _embed_query_override is not None:
        return _embed_query_override(query)

    return get_llm_gateway(settings).embed_query(query)


def _normalize_role_ids(role_ids: Sequence[str] | str) -> list[str]:
    if isinstance(role_ids, str):
        rid = role_ids.strip()
        return [rid] if rid else []
    normalized: list[str] = []
    seen: set[str] = set()
    for raw in role_ids:
        rid = str(raw).strip()
        if not rid or rid in seen:
            continue
        seen.add(rid)
        normalized.append(rid)
    return normalized


def _mock_retrieve(role_ids: Sequence[str], query: str, *, top_k: int) -> list[RagChunk]:
    if not query:
        return []
    allowed = set(_normalize_role_ids(role_ids))
    chunks = [
        c
        for c in _MOCK_CHUNKS
        if _MOCK_ROLE_BY_DOC.get(c.doc_id) in allowed
    ]
    return chunks[:top_k]


def _candidate_from_mapping(item: RagCandidate | dict[str, Any]) -> RagCandidate:
    if isinstance(item, RagCandidate):
        return item
    return RagCandidate(
        doc_id=str(item["doc_id"]),
        chunk_id=str(item["chunk_id"]),
        text=str(item["text"]),
        score=float(item.get("score", 0.0)),
        channel=str(item.get("channel") or "dense"),  # type: ignore[arg-type]
    )


def _candidate_to_mapping(item: RagCandidate) -> dict[str, Any]:
    return {
        "doc_id": item.doc_id,
        "chunk_id": item.chunk_id,
        "text": item.text,
        "score": item.score,
        "channel": item.channel,
    }


def _merge_candidates(*groups: Sequence[dict[str, Any] | RagCandidate]) -> list[dict[str, Any]]:
    """Compatibility wrapper for the old dict-shaped merge helper."""
    candidate_groups = [[_candidate_from_mapping(item) for item in group] for group in groups]
    return [_candidate_to_mapping(item) for item in merge_candidates(*candidate_groups)]


def _store(client: QdrantClient, *, collection: str) -> QdrantKbStore:
    return QdrantKbStore(client=client, collection=collection)


def _dense_search(
    client: QdrantClient,
    *,
    collection: str,
    role_ids: Sequence[str],
    query_vector: list[float],
    limit: int,
) -> list[dict[str, Any]]:
    return [
        _candidate_to_mapping(item)
        for item in _store(client, collection=collection).dense_search(
            role_ids=role_ids,
            query_vector=query_vector,
            limit=limit,
        )
    ]


def _sparse_search(
    client: QdrantClient,
    *,
    collection: str,
    role_ids: Sequence[str],
    query: str,
    limit: int,
) -> list[dict[str, Any]]:
    return [
        _candidate_to_mapping(item)
        for item in _store(client, collection=collection).lexical_search(
            role_ids=role_ids,
            query=query,
            limit=limit,
        )
    ]


def _text_search(
    client: QdrantClient,
    *,
    collection: str,
    role_ids: Sequence[str],
    query: str,
    limit: int,
) -> list[dict[str, Any]]:
    return [
        _candidate_to_mapping(item)
        for item in _store(client, collection=collection).text_search(
            role_ids=role_ids,
            query=query,
            limit=limit,
        )
    ]


def _bm25_search(
    client: QdrantClient,
    *,
    collection: str,
    role_ids: Sequence[str],
    query: str,
    limit: int,
) -> list[dict[str, Any]]:
    return [
        _candidate_to_mapping(item)
        for item in _store(client, collection=collection).bm25_search(
            role_ids=role_ids,
            query=query,
            limit=limit,
        )
    ]


def _rerank_candidates_impl(
    query: str,
    candidates: Sequence[dict[str, Any] | RagCandidate],
    *,
    top_k: int,
    settings: Settings | None = None,
) -> list[RagChunk]:
    if not candidates:
        return []

    cfg = settings or get_settings()
    limit = min(len(candidates), cfg.RERANK_TOP_K)
    pool = [_candidate_from_mapping(c) for c in candidates[:limit]]
    documents = [c.text for c in pool]

    if _reranker_override is not None:
        scores = _reranker_override(query, documents)
    else:
        scores = default_rerank(query, documents, settings=cfg)

    if len(scores) != len(pool):
        scores = [float(len(pool) - i) for i in range(len(pool))]

    ranked = sorted(zip(pool, scores), key=lambda pair: float(pair[1]), reverse=True)
    chunks: list[RagChunk] = []
    for item, score in ranked[:top_k]:
        chunks.append(
            RagChunk(
                doc_id=item.doc_id,
                chunk_id=item.chunk_id,
                text=item.text,
                score=float(score),
                channel=item.channel,
                metadata=item.metadata,
            )
        )
    return chunks


@rerank_traceable()
def rerank_candidates(
    query: str,
    candidates: Sequence[dict[str, Any] | RagCandidate],
    *,
    top_k: int,
    settings: Settings | None = None,
) -> list[RagChunk]:
    return _rerank_candidates_impl(query, candidates, top_k=top_k, settings=settings)


def _service_rerank(
    query: str,
    candidates: list[RagCandidate],
    top_k: int,
    settings: Settings,
) -> list[RagChunk]:
    return _rerank_candidates_impl(query, candidates, top_k=top_k, settings=settings)


@retrieve_traceable()
def retrieve(
    role_ids: Sequence[str] | str,
    query: str,
    *,
    top_k: int | None = None,
    second_pass: bool = False,
    settings: Settings | None = None,
) -> list[RagChunk]:
    """
    Retrieve KB chunks for bound ``role_ids`` using hybrid search + rerank.

    Documents whose payload ``role_ids[]`` intersect bound roles are eligible (M1 ``role_id`` fallback).
    Returns ``[]`` for empty query, unknown roles (mock), empty collection, or errors.
    When ``QDRANT_MOCK`` is true, returns in-memory fixtures without network I/O.
    """
    cfg = settings or get_settings()
    roles = _normalize_role_ids(role_ids)
    q = _text(query)
    if not roles or not q:
        return []

    final_k = top_k if top_k is not None else cfg.RERANK_TOP_K

    if cfg.QDRANT_MOCK:
        chunks = _mock_retrieve(roles, q, top_k=final_k)
        metadata = build_retrieval_metadata(
            role_ids=roles,
            query=q,
            dense_count=0,
            sparse_count=0,
            result_count=len(chunks),
            mock=True,
            second_pass=second_pass,
        )
        emit_event(ObservabilityEventType.RAG_RETRIEVED, metadata)
        return chunks

    client = _get_qdrant_client(cfg)
    service = RagRetrievalService(
        store=QdrantKbStore(client=client, collection=cfg.QDRANT_COLLECTION_KB),
        embed_query=_embed_query,
        rerank=_service_rerank,
        settings=cfg,
    )
    prefetch_limit = max(final_k, cfg.RERANK_TOP_K)
    result = service.retrieve(
        RagQueryPlan(
            role_ids=tuple(roles),
            query=q,
            top_k=final_k,
            prefetch_limit=prefetch_limit,
            second_pass=second_pass,
        )
    )
    return list(result.chunks)


def rag_retrieval_node(state: RagRetrievalNodeState) -> dict[str, list[RagChunk]]:
    """LangGraph node: populate ``rag_chunks`` from ``rewritten_query`` + ``role_ids``."""
    if state.get("rag_skipped"):
        return {"rag_chunks": []}

    role_ids = _normalize_role_ids(state.get("role_ids") or [])
    query = _text(state.get("rewritten_query"))
    if not role_ids or not query:
        return {"rag_chunks": []}

    return {"rag_chunks": retrieve(role_ids, query)}
