"""Typed internal RAG values used below the public retriever facade."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

from contracts.rag import RagChannel


@dataclass(frozen=True)
class RagQueryPlan:
    """Role-scoped retrieval plan for one query."""

    role_ids: tuple[str, ...]
    query: str
    top_k: int
    prefetch_limit: int
    second_pass: bool = False


@dataclass(frozen=True)
class RagCandidate:
    """Internal candidate before final rerank."""

    doc_id: str
    chunk_id: str
    text: str
    score: float
    channel: RagChannel
    metadata: dict[str, Any] | None = None

    def with_score(self, score: float, *, channel: RagChannel | None = None) -> "RagCandidate":
        return replace(self, score=score, channel=channel or self.channel)
