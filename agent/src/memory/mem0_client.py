"""Local mem0 (OSS Memory + Qdrant) read/write client for user preference facts."""

from __future__ import annotations

from collections.abc import Callable
from functools import lru_cache
from pathlib import Path
from typing import Any

from openai import OpenAI

from contracts.llm import ModelUseCase
from infrastructure.llm.policy import chat_policy, embedding_policy
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
    if not (settings.MEM0_LLM_MODEL_NAME or "").strip():
        raise ValueError("MEM0_LLM_MODEL_NAME must be configured for mem0 infer writes")
    llm_policy = chat_policy(ModelUseCase.MEM0_WRITE, settings)
    embed_policy = embedding_policy(settings)
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
                "model": llm_policy.model_name,
                "api_key": settings.OPENAI_API_KEY,
                "openai_base_url": settings.OPENAI_BASE_URL,
                "temperature": llm_policy.temperature,
                "max_tokens": llm_policy.max_tokens,
            },
        },
        "embedder": {
            "provider": "openai",
            "config": {
                "model": embed_policy.model_name,
                "api_key": settings.OPENAI_API_KEY,
                "openai_base_url": settings.OPENAI_BASE_URL,
                "embedding_dims": embed_policy.dimensions,
            },
        },
    }
    instructions = _load_custom_instructions()
    if instructions:
        config["custom_instructions"] = instructions
    return config


def _apply_mem0_openai_timeout(memory: Any, settings: Settings) -> None:
    """Apply HTTP timeout to the mem0 OpenAI client used by infer=True writes."""
    memory.llm.client = OpenAI(
        api_key=settings.OPENAI_API_KEY,
        base_url=settings.OPENAI_BASE_URL,
        timeout=settings.MEM0_LLM_TIMEOUT_SECONDS,
    )


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

        settings = get_settings()
        _memory_instance = Memory.from_config(build_mem0_config(settings))
        _apply_mem0_openai_timeout(_memory_instance, settings)
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


def fetch_user_memories(user_id: str, *, query: str | None = None) -> list[str]:
    """Load user memory facts from LangGraph Store (delegates to ``memory.read``)."""
    from memory.read import MemoryUserIdError, fetch_user_memories as fetch_from_store

    try:
        return fetch_from_store(user_id, query=query)
    except MemoryUserIdError as exc:
        raise Mem0UserIdError(str(exc)) from exc


async def afetch_user_memories(
    user_id: str,
    *,
    query: str | None = None,
) -> list[str]:
    """Async wrapper around :func:`fetch_user_memories` (thread offload)."""
    from memory.read import afetch_user_memories as afetch_from_store

    return await afetch_from_store(user_id, query=query)


def format_mem0_for_system(memories: list[str]) -> str:
    """Format memory facts for injection into the system prompt."""
    facts = [m.strip() for m in memories if m and m.strip()]
    if not facts:
        return ""
    lines = ["## User preferences (from memory)", ""]
    lines.extend(f"- {fact}" for fact in facts)
    return "\n".join(lines)
