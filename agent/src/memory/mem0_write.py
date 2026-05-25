"""Post-turn mem0 writes via local OSS Memory + Qdrant (legacy; task 73 removes)."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from contracts.memory_write import StructuredMemoryRecord
from memory.write import (
    MemoryWriteResult,
    extract_and_store as store_extract_and_store,
    reset_write_overrides,
    set_manager_invoke_fn,
    store_structured_record as store_structured_profile,
    turn_messages_for_extraction,
)

Mem0WriteResult = MemoryWriteResult


def set_mem0_add_fn(fn: Callable[..., Any] | None) -> None:
    """Test shim: map legacy mem0 ``add`` mocks to langmem manager invoke."""
    if fn is None:
        set_manager_invoke_fn(None)
        return

    def _invoke(
        messages: Sequence[BaseMessage],
        *,
        user_id: str,
    ) -> list[dict[str, Any]]:
        payload = turn_messages_to_mem0_payload(messages)
        raw = fn(payload, user_id=user_id, infer=True)
        return _mem0_add_result_to_puts(raw)

    set_manager_invoke_fn(_invoke)


def reset_mem0_write_overrides() -> None:
    reset_write_overrides()


def turn_messages_to_mem0_payload(
    turn_messages: Sequence[BaseMessage],
) -> list[dict[str, str]]:
    """Map LangChain turn messages to mem0 ``add`` message dicts (user/assistant only)."""
    payload: list[dict[str, str]] = []
    for message in turn_messages_for_extraction(turn_messages):
        content = str(message.content).strip()
        if isinstance(message, HumanMessage):
            payload.append({"role": "user", "content": content})
        elif isinstance(message, AIMessage):
            payload.append({"role": "assistant", "content": content})
    return payload


def store_structured_record(
    user_id: str,
    record: StructuredMemoryRecord,
) -> Mem0WriteResult:
    """Store a structured profile record via LangGraph Store (delegates to ``memory.write``)."""
    return store_structured_profile(user_id, record)


def extract_and_store(
    user_id: str,
    turn_messages: Sequence[BaseMessage],
    *,
    model_name: str | None = None,
) -> Mem0WriteResult:
    """Store one turn via langmem inferred extraction (delegates to ``memory.write``)."""
    return store_extract_and_store(user_id, turn_messages, model_name=model_name)


def _mem0_add_result_to_puts(raw: object) -> list[dict[str, Any]]:
    from memory.mem0_client import parse_memories_from_get_all

    memories = parse_memories_from_get_all(raw)
    return [
        {
            "namespace": ("users", "legacy", "facts"),
            "key": f"mem-{index}",
            "value": {"kind": "Memory", "content": {"content": memory}},
        }
        for index, memory in enumerate(memories)
    ]
