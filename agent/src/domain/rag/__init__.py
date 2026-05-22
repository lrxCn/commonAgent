"""RAG domain logic: query planning, lexical scoring, merge, and service orchestration."""

from domain.rag.formatting import format_rag_chunks_for_system, rag_chunk_to_dict
from domain.rag.merge import merge_candidates
from domain.rag.models import RagCandidate, RagQueryPlan
from domain.rag.service import RagRetrievalService, build_retrieval_metadata

__all__ = [
    "RagCandidate",
    "RagQueryPlan",
    "RagRetrievalService",
    "build_retrieval_metadata",
    "format_rag_chunks_for_system",
    "merge_candidates",
    "rag_chunk_to_dict",
]
