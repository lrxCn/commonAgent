"""Candidate merge logic for multi-channel RAG retrieval."""

from __future__ import annotations

from collections.abc import Sequence

from domain.rag.models import RagCandidate


def merge_candidates(*groups: Sequence[RagCandidate]) -> list[RagCandidate]:
    """RRF-style merge by chunk_id across dense and lexical channels."""
    merged: dict[str, RagCandidate] = {}
    scores: dict[str, float] = {}
    rank_constant = 60
    for group in groups:
        for rank, item in enumerate(group, start=1):
            key = item.chunk_id
            rrf = 1.0 / (rank_constant + rank)
            if key not in merged:
                merged[key] = item.with_score(rrf)
                scores[key] = rrf
                continue
            scores[key] += rrf
            existing = merged[key]
            preferred = item if item.score > existing.score else existing
            merged[key] = preferred.with_score(scores[key], channel=existing.channel)
    return sorted(merged.values(), key=lambda item: item.score, reverse=True)
