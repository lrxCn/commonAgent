"""LangGraph Store write path for structured and inferred user memory (tasks 71+)."""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from contracts.memory_store import profile_namespace
from contracts.memory_write import StructuredMemoryRecord
from memory.langmem_manager import get_memory_store_manager, reset_memory_store_manager
from memory.store import get_pooled_store
from observability.tracing import attach_run_metadata
from settings.config import get_settings

logger = logging.getLogger(__name__)

_store_put_override: Callable[..., Any] | None = None
_manager_invoke_override: Callable[..., list[dict[str, Any]]] | None = None


class MemoryUserIdError(ValueError):
    """Raised when user_id is missing or blank for memory writes."""


def _require_user_id(user_id: str | None) -> str:
    if user_id is None or not str(user_id).strip():
        raise MemoryUserIdError("user_id is required to store user memories")
    return str(user_id).strip()


@dataclass(frozen=True)
class MemoryWriteResult:
    status: str
    stored_memories: tuple[str, ...] = ()
    reason: str = ""

    @property
    def stored_count(self) -> int:
        return len(self.stored_memories)


def set_store_put_fn(fn: Callable[..., Any] | None) -> None:
    """Replace Store ``put`` call for tests; pass None to clear."""
    global _store_put_override
    _store_put_override = fn


def set_manager_invoke_fn(
    fn: Callable[..., list[dict[str, Any]]] | None,
) -> None:
    """Replace langmem manager ``invoke`` for tests; pass None to clear."""
    global _manager_invoke_override
    _manager_invoke_override = fn


def reset_write_overrides() -> None:
    set_store_put_fn(None)
    set_manager_invoke_fn(None)
    reset_memory_store_manager()


def turn_messages_for_extraction(
    turn_messages: Sequence[BaseMessage],
) -> list[BaseMessage]:
    """Keep user/assistant LangChain messages with non-empty content."""
    messages: list[BaseMessage] = []
    for message in turn_messages:
        content = str(message.content).strip() if message.content else ""
        if not content:
            continue
        if isinstance(message, (HumanMessage, AIMessage)):
            messages.append(message)
    return messages


def _memory_write_mock_enabled() -> bool:
    settings = get_settings()
    return settings.MEMORY_STORE_MOCK or settings.MEM0_MOCK


def extract_and_store(
    user_id: str,
    turn_messages: Sequence[BaseMessage],
    *,
    model_name: str | None = None,
) -> MemoryWriteResult:
    """Extract inferred facts via langmem store manager and write to collection."""
    del model_name  # resolved via LLM Gateway / MEMORY_EXTRACT policy
    uid = _require_user_id(user_id)
    trace_metadata = {"memory_write.mode": "inferred"}

    if _memory_write_mock_enabled():
        result = MemoryWriteResult(status="skipped_mock")
        _attach_write_metadata(result, trace_metadata)
        return result

    messages = turn_messages_for_extraction(turn_messages)
    if not messages:
        result = MemoryWriteResult(status="skipped_empty_payload")
        _attach_write_metadata(result, trace_metadata)
        return result

    try:
        if _manager_invoke_override is not None:
            puts = _manager_invoke_override(
                messages,
                user_id=uid,
            )
        else:
            manager = get_memory_store_manager()
            puts = manager.invoke(
                {"messages": messages, "max_steps": 1},
                config={"configurable": {"user_id": uid}},
            )
    except MemoryUserIdError:
        raise
    except Exception as exc:
        result = MemoryWriteResult(status="failed", reason=type(exc).__name__)
        logger.exception(
            "memory_store.inferred_store_failed",
            extra={"user_id": uid, "reason": result.reason},
        )
        _attach_write_metadata(result, trace_metadata)
        return result

    stored = _stored_memories_from_puts(puts)
    if stored:
        result = MemoryWriteResult(status="stored", stored_memories=tuple(stored))
        logger.info(
            "memory_store.stored_inferred",
            extra={"user_id": uid, "count": len(stored)},
        )
    else:
        result = MemoryWriteResult(status="stored_empty")
    _attach_write_metadata(result, trace_metadata)
    return result


def _stored_memories_from_puts(puts: list[dict[str, Any]]) -> list[str]:
    stored: list[str] = []
    seen: set[str] = set()
    for put in puts:
        value = put.get("value")
        text = _memory_text_from_store_value(value)
        if text and text not in seen:
            stored.append(text)
            seen.add(text)
    return stored


def _memory_text_from_store_value(value: object) -> str:
    if isinstance(value, dict):
        content = value.get("content")
        if isinstance(content, dict):
            for key in ("content", "text", "memory"):
                raw = content.get(key)
                if raw is not None and str(raw).strip():
                    return str(raw).strip()
        if content is not None and str(content).strip():
            return str(content).strip()
        for key in ("text", "memory"):
            raw = value.get(key)
            if raw is not None and str(raw).strip():
                return str(raw).strip()
    if isinstance(value, str) and value.strip():
        return value.strip()
    return ""


def store_structured_record(
    user_id: str,
    record: StructuredMemoryRecord,
) -> MemoryWriteResult:
    """Upsert a structured profile field into LangGraph Store (no mem0 API)."""
    from memory.structured_record import canonical_fact_text

    uid = _require_user_id(user_id)
    settings = get_settings()
    canonical = canonical_fact_text(record)
    trace_metadata = _structured_trace_metadata(record)

    if not canonical.strip():
        result = MemoryWriteResult(status="skipped_empty_payload")
        _attach_write_metadata(result, trace_metadata)
        return result

    if settings.MEMORY_STORE_MOCK:
        result = MemoryWriteResult(status="stored", stored_memories=(canonical,))
        logger.info(
            "memory_store.stored_structured_mock",
            extra={"user_id": uid, "attribute": record.attribute},
        )
        _attach_write_metadata(result, trace_metadata)
        return result

    payload = _profile_store_payload(record, canonical=canonical)
    namespace = profile_namespace(uid)
    try:
        if _store_put_override is not None:
            _store_put_override(namespace, record.attribute, payload)
        else:
            store = get_pooled_store()
            store.put(namespace, record.attribute, payload)
    except MemoryUserIdError:
        raise
    except Exception as exc:
        result = MemoryWriteResult(status="failed", reason=type(exc).__name__)
        logger.exception(
            "memory_store.structured_store_failed",
            extra={
                "user_id": uid,
                "attribute": record.attribute,
                "reason": result.reason,
            },
        )
        _attach_write_metadata(result, trace_metadata)
        return result

    result = MemoryWriteResult(status="stored", stored_memories=(canonical,))
    logger.info(
        "memory_store.stored_structured",
        extra={"user_id": uid, "attribute": record.attribute, "count": 1},
    )
    _attach_write_metadata(result, trace_metadata)
    return result


def _profile_store_payload(
    record: StructuredMemoryRecord,
    *,
    canonical: str,
) -> dict[str, str]:
    return {
        "value": record.value,
        "raw_utterance": record.raw_utterance,
        "source_turn_id": record.source_turn_id,
        "extraction_method": record.extraction_method,
        "canonical": canonical,
        "updated_at": datetime.now(tz=UTC).isoformat(),
    }


def _structured_trace_metadata(record: StructuredMemoryRecord) -> dict[str, object]:
    return {
        "memory_write.mode": "structured",
        "memory_write.record.attribute": record.attribute,
        "memory_write.record.value_hash": _hash_record_value(record.value),
        "memory_write.extraction_method": record.extraction_method,
    }


def _hash_record_value(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def _attach_write_metadata(
    result: MemoryWriteResult,
    extra: dict[str, object],
) -> None:
    attach_run_metadata(
        {
            **extra,
            "memory_store.status": result.status,
            "memory_store.reason": result.reason,
            "memory_store.stored_count": result.stored_count,
            "mem0_write.status": result.status,
            "mem0_write.reason": result.reason,
            "mem0_write.stored_count": result.stored_count,
        }
    )
