"""Local mem0 (OSS Memory + Qdrant) read/write client for user preference facts."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from functools import lru_cache
from pathlib import Path
from typing import Any

from settings.config import Settings, get_settings

_CUSTOM_INSTRUCTIONS_PATH = (
    Path(__file__).parent / "prompts" / "mem0_custom_instructions.txt"
)

_memory_instance: Any | None = None
_memory_factory: Callable[[], Any] | None = None


class Mem0UserIdError(ValueError):
    """Raised when user_id is missing or blank for mem0 operations."""


def set_memory_factory(factory: Callable[[], Any] | None) -> None:
    """Replace Memory construction for tests; pass None to clear."""
    global _memory_factory, _memory_instance
    _memory_factory = factory
    _memory_instance = None


def reset_mem0_memory() -> None:
    """Clear cached Memory instance and factory (for tests)."""
    set_memory_factory(None)


@lru_cache
def _load_custom_instructions() -> str:
    return _CUSTOM_INSTRUCTIONS_PATH.read_text(encoding="utf-8").strip()


def build_mem0_config(settings: Settings) -> dict[str, Any]:
    """Build mem0 OSS config: Qdrant vector store + OpenAI-compatible LLM/embedder."""
    config: dict[str, Any] = {
        "vector_store": {
            "provider": "qdrant",
            "config": {
                "collection_name": settings.QDRANT_COLLECTION_MEM0,
                "host": settings.QDRANT_HOST,
                "port": settings.QDRANT_PORT,
                "embedding_model_dims": settings.EMBEDDING_MODEL_DIMS,
            },
        },
        "llm": {
            "provider": "openai",
            "config": {
                "model": settings.OPENAI_MODEL_NAME,
                "api_key": settings.OPENAI_API_KEY,
                "openai_base_url": settings.OPENAI_BASE_URL,
                "temperature": 0.1,
            },
        },
        "embedder": {
            "provider": "openai",
            "config": {
                "model": settings.EMBEDDING_MODEL,
                "api_key": settings.OPENAI_API_KEY,
                "openai_base_url": settings.OPENAI_BASE_URL,
                "embedding_dims": settings.EMBEDDING_MODEL_DIMS,
            },
        },
    }
    instructions = _load_custom_instructions()
    if instructions:
        config["custom_instructions"] = instructions
    return config


def _require_user_id(user_id: str | None) -> str:
    if user_id is None or not str(user_id).strip():
        raise Mem0UserIdError("user_id is required to fetch mem0 memories")
    return str(user_id).strip()


def get_local_memory() -> Any:
    """Return the shared local OSS ``Memory`` instance (tests may override factory)."""
    global _memory_instance
    if _memory_factory is not None:
        return _memory_factory()
    if _memory_instance is None:
        from mem0 import Memory

        _memory_instance = Memory.from_config(build_mem0_config(get_settings()))
    return _memory_instance


def _get_memory() -> Any:
    return get_local_memory()


def parse_memories_from_get_all(raw: Any) -> list[str]:
    """Extract memory text strings from mem0 ``get_all`` response."""
    items: list[Any]
    if isinstance(raw, dict):
        results = raw.get("results")
        items = list(results) if isinstance(results, list) else []
    elif isinstance(raw, list):
        items = raw
    else:
        return []

    memories: list[str] = []
    for item in items:
        if isinstance(item, str):
            text = item.strip()
        elif isinstance(item, dict):
            value = item.get("memory")
            text = str(value).strip() if value is not None else ""
        else:
            continue
        if text:
            memories.append(text)
    return memories


def fetch_user_memories(user_id: str) -> list[str]:
    """Load extracted preference facts for ``user_id`` from local mem0 + Qdrant."""
    uid = _require_user_id(user_id)
    settings = get_settings()
    if settings.MEM0_MOCK:
        return []

    memory = _get_memory()
    raw = memory.get_all(
        filters={"user_id": uid},
        top_k=settings.MEM0_READ_LIMIT,
    )
    return parse_memories_from_get_all(raw)


async def afetch_user_memories(user_id: str) -> list[str]:
    """Async wrapper around :func:`fetch_user_memories` (thread offload)."""
    return await asyncio.to_thread(fetch_user_memories, user_id)


def format_mem0_for_system(memories: list[str]) -> str:
    """Format memory facts for injection into the system prompt."""
    facts = [m.strip() for m in memories if m and m.strip()]
    if not facts:
        return ""
    lines = ["## User preferences (from memory)", ""]
    lines.extend(f"- {fact}" for fact in facts)
    return "\n".join(lines)
