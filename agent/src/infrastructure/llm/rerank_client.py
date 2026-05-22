"""Compatibility rerank facade over the LLM gateway."""

from __future__ import annotations

from infrastructure.llm.gateway import get_llm_gateway
from settings.config import Settings, get_settings


def default_rerank(query: str, documents: list[str], *, settings: Settings | None = None) -> list[float]:
    """Rerank via the central LLM gateway."""
    if not documents:
        return []
    cfg = settings or get_settings()
    return get_llm_gateway(cfg).rerank(query, documents)
