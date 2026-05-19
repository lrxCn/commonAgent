"""RAG retrieval: Qdrant role_id filter + dense/sparse hybrid + rerank."""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass
from typing import Any, TypedDict

from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels
from observability.tracing import attach_run_metadata, rerank_traceable, retrieve_traceable
from settings.config import Settings, get_settings

logger = logging.getLogger(__name__)

# Qdrant vector names (aligned with future ingest in task 20)
_DENSE_VECTOR_NAME = "dense"

RerankFn = Callable[[str, list[str]], list[float]]

_qdrant_client_override: QdrantClient | None = None
_reranker_override: RerankFn | None = None
_embed_query_override: Callable[[str], list[float]] | None = None


@dataclass(frozen=True)
class RagChunk:
    """Single retrieved knowledge chunk with citation identifiers."""

    doc_id: str
    chunk_id: str
    text: str
    score: float


class RagRetrievalNodeState(TypedDict, total=False):
    """Minimal state slice for rag_retrieval_node."""

    role_id: str
    rewritten_query: str
    rag_skipped: bool
    rag_chunks: list[RagChunk]


# Mock fixtures for QDRANT_MOCK (filtered by role_id at runtime)
_MOCK_CHUNKS: tuple[RagChunk, ...] = (
    RagChunk(
        doc_id="doc-reimbursement",
        chunk_id="chunk-001",
        text="报销制度：差旅费需在出差结束后 30 日内提交审批。",
        score=0.92,
    ),
    RagChunk(
        doc_id="doc-reimbursement",
        chunk_id="chunk-002",
        text="报销制度：单笔超过 5000 元需部门负责人加签。",
        score=0.88,
    ),
    RagChunk(
        doc_id="doc-leave",
        chunk_id="chunk-010",
        text="年假规则：工作满一年享有 5 天带薪年假。",
        score=0.85,
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


def _role_filter(role_id: str) -> qmodels.Filter:
    return qmodels.Filter(
        must=[
            qmodels.FieldCondition(
                key="role_id",
                match=qmodels.MatchValue(value=role_id),
            )
        ]
    )


def _payload_text(payload: dict[str, Any]) -> str:
    for key in ("text", "content", "chunk_text"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _hit_to_candidate(hit: Any, *, channel: str) -> dict[str, Any] | None:
    payload = hit.payload if isinstance(hit.payload, dict) else {}
    doc_id = str(payload.get("doc_id") or "").strip()
    chunk_id = str(payload.get("chunk_id") or hit.id or "").strip()
    text = _payload_text(payload)
    if not doc_id or not chunk_id or not text:
        return None
    score = float(hit.score) if hit.score is not None else 0.0
    return {
        "doc_id": doc_id,
        "chunk_id": chunk_id,
        "text": text,
        "score": score,
        "channel": channel,
    }


def _merge_candidates(*groups: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    """RRF-style merge by chunk_id across dense/sparse channels."""
    merged: dict[str, dict[str, Any]] = {}
    rank_constant = 60
    for group in groups:
        for rank, item in enumerate(group, start=1):
            key = item["chunk_id"]
            rrf = 1.0 / (rank_constant + rank)
            if key not in merged:
                merged[key] = {**item, "score": rrf}
            else:
                merged[key]["score"] = float(merged[key]["score"]) + rrf
                if item["score"] > merged[key].get("channel_score", 0.0):
                    merged[key]["channel_score"] = item["score"]
    return sorted(merged.values(), key=lambda x: float(x["score"]), reverse=True)


def _mock_retrieve(role_id: str, query: str, *, top_k: int) -> list[RagChunk]:
    if not query:
        return []
    chunks = [
        c
        for c in _MOCK_CHUNKS
        if _MOCK_ROLE_BY_DOC.get(c.doc_id) == role_id
    ]
    return chunks[:top_k]


def _get_qdrant_client(settings: Settings) -> QdrantClient:
    if _qdrant_client_override is not None:
        return _qdrant_client_override
    return QdrantClient(url=settings.qdrant_url, prefer_grpc=False)


def _collection_has_sparse(client: QdrantClient, collection_name: str) -> bool:
    try:
        info = client.get_collection(collection_name)
        config = info.config.params if info.config else None  # type: ignore[union-attr]
        if config is None:
            return False
        sparse_vectors = getattr(config, "sparse_vectors", None)
        return bool(sparse_vectors)
    except Exception:
        return False


def _embed_query(query: str, settings: Settings) -> list[float]:
    if _embed_query_override is not None:
        return _embed_query_override(query)

    from langchain_openai import OpenAIEmbeddings

    embeddings = OpenAIEmbeddings(
        model=settings.EMBEDDING_MODEL,
        api_key=settings.OPENAI_API_KEY,
        base_url=settings.OPENAI_BASE_URL,
        dimensions=settings.EMBEDDING_MODEL_DIMS,
    )
    vector = embeddings.embed_query(query)
    return list(vector)


def _dense_search(
    client: QdrantClient,
    *,
    collection: str,
    role_id: str,
    query_vector: list[float],
    limit: int,
) -> list[dict[str, Any]]:
    try:
        hits = client.search(
            collection_name=collection,
            query_vector=(_DENSE_VECTOR_NAME, query_vector),
            query_filter=_role_filter(role_id),
            limit=limit,
            with_payload=True,
        )
    except Exception:
        try:
            hits = client.search(
                collection_name=collection,
                query_vector=query_vector,
                query_filter=_role_filter(role_id),
                limit=limit,
                with_payload=True,
            )
        except Exception:
            logger.debug("dense search failed for collection %s", collection, exc_info=True)
            return []

    candidates: list[dict[str, Any]] = []
    for hit in hits:
        item = _hit_to_candidate(hit, channel="dense")
        if item:
            candidates.append(item)
    return candidates


def _sparse_search(
    client: QdrantClient,
    *,
    collection: str,
    role_id: str,
    query: str,
    limit: int,
) -> list[dict[str, Any]]:
    """
    Sparse / keyword channel.

    Uses Qdrant sparse vectors when configured; otherwise full-text match on payload.
    Query sparse embedding is provided by ingest (task 20); until then text match applies.
    """
    if _collection_has_sparse(client, collection):
        logger.debug(
            "collection %s has sparse vectors; text match used until ingest wires query sparse",
            collection,
        )
    return _text_search(client, collection=collection, role_id=role_id, query=query, limit=limit)


def _text_search(
    client: QdrantClient,
    *,
    collection: str,
    role_id: str,
    query: str,
    limit: int,
) -> list[dict[str, Any]]:
    """Keyword-style fallback when sparse vectors are not configured."""
    if not query:
        return []
    try:
        records, _ = client.scroll(
            collection_name=collection,
            scroll_filter=qmodels.Filter(
                must=[
                    qmodels.FieldCondition(
                        key="role_id",
                        match=qmodels.MatchValue(value=role_id),
                    ),
                    qmodels.FieldCondition(
                        key="text",
                        match=qmodels.MatchText(text=query),
                    ),
                ]
            ),
            limit=limit,
            with_payload=True,
        )
    except Exception:
        logger.debug("text scroll search failed", exc_info=True)
        return []

    candidates: list[dict[str, Any]] = []
    for point in records:
        payload = point.payload if isinstance(point.payload, dict) else {}
        doc_id = str(payload.get("doc_id") or "").strip()
        chunk_id = str(payload.get("chunk_id") or point.id or "").strip()
        text = _payload_text(payload)
        if not doc_id or not chunk_id or not text:
            continue
        candidates.append(
            {
                "doc_id": doc_id,
                "chunk_id": chunk_id,
                "text": text,
                "score": 0.5,
                "channel": "text",
            }
        )
    return candidates


def default_rerank(query: str, documents: list[str], *, settings: Settings | None = None) -> list[float]:
    """Rerank via SiliconFlow / OpenAI-compatible ``/rerank`` endpoint."""
    if not documents:
        return []

    cfg = settings or get_settings()
    payload = {
        "model": cfg.RERANK_MODEL,
        "query": query,
        "documents": documents,
        "top_n": len(documents),
    }
    url = f"{cfg.OPENAI_BASE_URL.rstrip('/')}/rerank"
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {cfg.OPENAI_API_KEY}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, json.JSONDecodeError, TimeoutError):
        logger.debug("rerank API failed; using retrieval order", exc_info=True)
        return [float(len(documents) - i) for i in range(len(documents))]

    results = body.get("results") if isinstance(body, dict) else None
    if not isinstance(results, list):
        return [float(len(documents) - i) for i in range(len(documents))]

    scores = [0.0] * len(documents)
    for item in results:
        if not isinstance(item, dict):
            continue
        index = item.get("index")
        score = item.get("relevance_score", item.get("score"))
        if isinstance(index, int) and 0 <= index < len(documents) and score is not None:
            scores[index] = float(score)
    if all(s == 0.0 for s in scores):
        return [float(len(documents) - i) for i in range(len(documents))]
    return scores


@rerank_traceable()
def rerank_candidates(
    query: str,
    candidates: Sequence[dict[str, Any]],
    *,
    top_k: int,
    settings: Settings | None = None,
) -> list[RagChunk]:
    if not candidates:
        return []

    cfg = settings or get_settings()
    limit = min(len(candidates), cfg.RERANK_TOP_K)
    pool = list(candidates)[:limit]
    documents = [str(c["text"]) for c in pool]

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
                doc_id=str(item["doc_id"]),
                chunk_id=str(item["chunk_id"]),
                text=str(item["text"]),
                score=float(score),
            )
        )
    return chunks


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
    """Span metadata for LangSmith (task 21)."""
    return {
        "rag.role_id": role_id,
        "rag.query_len": len(query),
        "rag.dense_hits": dense_count,
        "rag.sparse_hits": sparse_count,
        "rag.result_count": result_count,
        "rag.mock": mock,
        "rag.second_pass": second_pass,
    }


@retrieve_traceable()
def retrieve(
    role_id: str,
    query: str,
    *,
    top_k: int | None = None,
    second_pass: bool = False,
    settings: Settings | None = None,
) -> list[RagChunk]:
    """
    Retrieve KB chunks for ``role_id`` using hybrid search + rerank.

    Returns ``[]`` for empty query, unknown role (mock), empty collection, or errors.
    When ``QDRANT_MOCK`` is true, returns in-memory fixtures without network I/O.
    """
    cfg = settings or get_settings()
    rid = _text(role_id)
    q = _text(query)
    if not rid or not q:
        return []

    final_k = top_k if top_k is not None else cfg.RERANK_TOP_K

    if cfg.QDRANT_MOCK:
        chunks = _mock_retrieve(rid, q, top_k=final_k)
        metadata = build_retrieval_metadata(
            role_id=rid,
            query=q,
            dense_count=0,
            sparse_count=0,
            result_count=len(chunks),
            mock=True,
            second_pass=second_pass,
        )
        attach_run_metadata(metadata)
        return chunks

    client = _get_qdrant_client(cfg)
    collection = cfg.QDRANT_COLLECTION_KB
    prefetch_limit = max(final_k, cfg.RERANK_TOP_K)

    try:
        dense_vector = _embed_query(q, cfg)
    except Exception:
        logger.debug("query embedding failed", exc_info=True)
        return []

    dense_hits = _dense_search(
        client,
        collection=collection,
        role_id=rid,
        query_vector=dense_vector,
        limit=prefetch_limit,
    )
    sparse_hits = _sparse_search(
        client,
        collection=collection,
        role_id=rid,
        query=q,
        limit=prefetch_limit,
    )
    merged = _merge_candidates(dense_hits, sparse_hits)
    chunks = rerank_candidates(q, merged, top_k=final_k, settings=cfg)

    metadata = build_retrieval_metadata(
        role_id=rid,
        query=q,
        dense_count=len(dense_hits),
        sparse_count=len(sparse_hits),
        result_count=len(chunks),
        mock=False,
        second_pass=second_pass,
    )
    attach_run_metadata(metadata)
    return chunks


def format_rag_chunks_for_system(chunks: Sequence[RagChunk]) -> str:
    """Format chunks for system prompt with doc/chunk citation markers."""
    if not chunks:
        return ""
    lines = ["## Knowledge base excerpts", ""]
    for chunk in chunks:
        ref = f"[doc:{chunk.doc_id}/chunk:{chunk.chunk_id}]"
        lines.append(f"- {ref} {chunk.text}")
    return "\n".join(lines)


def rag_chunk_to_dict(chunk: RagChunk) -> dict[str, Any]:
    """Serialize for LangGraph state / JSON."""
    return asdict(chunk)


def rag_retrieval_node(state: RagRetrievalNodeState) -> dict[str, list[RagChunk]]:
    """LangGraph node: populate ``rag_chunks`` from ``rewritten_query`` + ``role_id``."""
    if state.get("rag_skipped"):
        return {"rag_chunks": []}

    role_id = _text(state.get("role_id"))
    query = _text(state.get("rewritten_query"))
    if not role_id or not query:
        return {"rag_chunks": []}

    return {"rag_chunks": retrieve(role_id, query)}
