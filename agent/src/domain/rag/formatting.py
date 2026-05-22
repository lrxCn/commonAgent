"""RAG formatting helpers for system prompts and graph state."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from contracts.rag import RagChunk


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
    return dict(chunk.to_dict())
