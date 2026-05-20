"""Post-turn mem0 writes via local OSS Memory + Qdrant (infer=True pipeline)."""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from memory.mem0_client import (
    Mem0UserIdError,
    get_local_memory,
    parse_memories_from_get_all,
    _require_user_id,
)
from settings.config import get_settings

logger = logging.getLogger(__name__)

_memory_add_override: Callable[..., Any] | None = None


def set_mem0_add_fn(fn: Callable[..., Any] | None) -> None:
    """Replace mem0 ``Memory.add`` call (tests). Pass None to clear."""
    global _memory_add_override
    _memory_add_override = fn


def reset_mem0_write_overrides() -> None:
    set_mem0_add_fn(None)


def turn_messages_to_mem0_payload(
    turn_messages: Sequence[BaseMessage],
) -> list[dict[str, str]]:
    """Map LangChain turn messages to mem0 ``add`` message dicts (user/assistant only)."""
    payload: list[dict[str, str]] = []
    for message in turn_messages:
        content = str(message.content).strip() if message.content else ""
        if not content:
            continue
        if isinstance(message, HumanMessage):
            payload.append({"role": "user", "content": content})
        elif isinstance(message, AIMessage):
            payload.append({"role": "assistant", "content": content})
    return payload


def extract_and_store(
    user_id: str,
    turn_messages: Sequence[BaseMessage],
    *,
    model_name: str | None = None,
) -> list[str]:
    """Store one turn via mem0 ``Memory.add(..., infer=True)``; returns new memory texts."""
    del model_name  # mem0 uses MemoryConfig LLM; kept for call-site compatibility
    uid = _require_user_id(user_id)
    settings = get_settings()
    if settings.MEM0_MOCK:
        return []

    payload = turn_messages_to_mem0_payload(turn_messages)
    if not payload:
        return []

    try:
        if _memory_add_override is not None:
            raw = _memory_add_override(payload, user_id=uid, infer=True)
        else:
            memory = get_local_memory()
            raw = memory.add(payload, user_id=uid, infer=True)
    except Mem0UserIdError:
        raise
    except Exception:
        logger.exception("mem0_write.store_failed", extra={"user_id": uid})
        return []

    stored = parse_memories_from_get_all(raw)
    if stored:
        logger.info(
            "mem0_write.stored",
            extra={"user_id": uid, "count": len(stored)},
        )
    return stored
