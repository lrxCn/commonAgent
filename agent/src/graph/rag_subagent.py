"""RagSubAgent: second-pass retrieval when primary ``rag_chunks`` are insufficient."""

from __future__ import annotations

import logging
from collections.abc import Sequence

from rag.retriever import RagChunk, retrieve
from settings.config import Settings, get_settings

logger = logging.getLogger(__name__)


def max_chunk_score(chunks: Sequence[RagChunk]) -> float:
    """Highest rerank score among chunks; 0.0 when empty."""
    if not chunks:
        return 0.0
    return max(float(c.score) for c in chunks)


def should_delegate_rag_subagent(
    *,
    rag_skipped: bool,
    rag_chunks: Sequence[RagChunk] | None,
    settings: Settings | None = None,
) -> bool:
    """
    Rule-based delegation (phase 1): empty primary results or max score below threshold.

    Skipped when the router bypassed RAG entirely.
    """
    if rag_skipped:
        return False
    chunks = list(rag_chunks or [])
    if not chunks:
        return True
    threshold = (settings or get_settings()).RAG_SUBAGENT_SCORE_THRESHOLD
    return max_chunk_score(chunks) < threshold


def merge_rag_chunks(
    primary: Sequence[RagChunk],
    secondary: Sequence[RagChunk],
    *,
    max_chunks: int | None = None,
    settings: Settings | None = None,
) -> list[RagChunk]:
    """Merge two retrieval passes, dedupe by ``chunk_id``, keep higher score, cap count."""
    cfg = settings or get_settings()
    limit = max_chunks if max_chunks is not None else cfg.RAG_CHUNKS_MAX

    merged: dict[str, RagChunk] = {}
    for chunk in (*primary, *secondary):
        existing = merged.get(chunk.chunk_id)
        if existing is None or float(chunk.score) > float(existing.score):
            merged[chunk.chunk_id] = chunk

    ranked = sorted(merged.values(), key=lambda c: float(c.score), reverse=True)
    return ranked[:limit]


def second_pass_top_k(settings: Settings | None = None) -> int:
    """Top-k for the second retrieval pass (larger than primary when configured)."""
    cfg = settings or get_settings()
    if cfg.RAG_SUBAGENT_TOP_K is not None:
        return int(cfg.RAG_SUBAGENT_TOP_K)
    return max(cfg.RERANK_TOP_K * 2, cfg.RERANK_TOP_K + 5)


def run_rag_subagent_retrieval(
    role_ids: list[str] | str,
    query: str,
    *,
    settings: Settings | None = None,
) -> list[RagChunk]:
    """Execute second-pass ``retrieve`` with trace metadata."""
    cfg = settings or get_settings()
    top_k = second_pass_top_k(cfg)
    chunks = retrieve(
        role_ids,
        query,
        top_k=top_k,
        second_pass=True,
        settings=cfg,
    )
    metadata = {
        "rag.second_pass": True,
        "rag.subagent_top_k": top_k,
        "rag.result_count": len(chunks),
    }
    logger.debug("rag subagent retrieval metadata: %s", metadata)
    return chunks


def apply_rag_subagent_merge(
    primary: Sequence[RagChunk],
    secondary: Sequence[RagChunk],
    *,
    settings: Settings | None = None,
) -> list[RagChunk]:
    """Merge primary and second-pass chunks into final ``rag_chunks``."""
    return merge_rag_chunks(primary, secondary, settings=settings)
