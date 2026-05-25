"""Post-turn mem0 writes via local OSS Memory + Qdrant."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import logging
from collections.abc import Callable, Sequence
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from contracts.memory_write import StructuredMemoryRecord
from memory.mem0_client import (
    Mem0UserIdError,
    get_local_memory,
    parse_memories_from_get_all,
    _require_user_id,
)
from observability.tracing import attach_run_metadata
from settings.config import get_settings

logger = logging.getLogger(__name__)

_memory_add_override: Callable[..., Any] | None = None


@dataclass(frozen=True)
class Mem0WriteResult:
    status: str
    stored_memories: tuple[str, ...] = ()
    reason: str = ""

    @property
    def stored_count(self) -> int:
        return len(self.stored_memories)


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


def store_structured_record(
    user_id: str,
    record: StructuredMemoryRecord,
) -> Mem0WriteResult:
    """Store a deterministic structured record via mem0 ``Memory.add(..., infer=False)``."""
    from memory.structured_record import canonical_fact_text

    uid = _require_user_id(user_id)
    settings = get_settings()
    canonical = canonical_fact_text(record)
    trace_metadata = _structured_trace_metadata(record)

    if not canonical.strip():
        result = Mem0WriteResult(status="skipped_empty_payload")
        _attach_write_metadata(result, trace_metadata)
        return result

    if settings.MEM0_MOCK:
        result = Mem0WriteResult(status="stored", stored_memories=(canonical,))
        logger.info(
            "mem0_write.stored_structured_mock",
            extra={"user_id": uid, "attribute": record.attribute},
        )
        _attach_write_metadata(result, trace_metadata)
        return result

    mem0_metadata = {
        "attribute": record.attribute,
        "source_turn_id": record.source_turn_id,
        "extraction_method": record.extraction_method,
    }
    try:
        if _memory_add_override is not None:
            raw = _memory_add_override(
                canonical,
                user_id=uid,
                infer=False,
                metadata=mem0_metadata,
            )
        else:
            memory = get_local_memory()
            raw = memory.add(
                canonical,
                user_id=uid,
                infer=False,
                metadata=mem0_metadata,
            )
    except Mem0UserIdError:
        raise
    except Exception as exc:
        result = Mem0WriteResult(status="failed", reason=type(exc).__name__)
        logger.exception(
            "mem0_write.structured_store_failed",
            extra={
                "user_id": uid,
                "attribute": record.attribute,
                "reason": result.reason,
            },
        )
        _attach_write_metadata(result, trace_metadata)
        return result

    stored = parse_memories_from_get_all(raw)
    result = Mem0WriteResult(status="stored", stored_memories=tuple(stored))
    if stored:
        logger.info(
            "mem0_write.stored_structured",
            extra={"user_id": uid, "attribute": record.attribute, "count": len(stored)},
        )
    else:
        result = Mem0WriteResult(status="stored_empty")
        logger.warning(
            "mem0_write.stored_structured_empty",
            extra={"user_id": uid, "attribute": record.attribute},
        )
    _attach_write_metadata(result, trace_metadata)
    return result


def extract_and_store(
    user_id: str,
    turn_messages: Sequence[BaseMessage],
    *,
    model_name: str | None = None,
) -> Mem0WriteResult:
    """Store one turn via mem0 ``Memory.add(..., infer=True)`` with structured status."""
    del model_name  # mem0 uses MemoryConfig LLM; kept for call-site compatibility
    uid = _require_user_id(user_id)
    settings = get_settings()
    if settings.MEM0_MOCK:
        result = Mem0WriteResult(status="skipped_mock")
        attach_run_metadata({"mem0_write.status": result.status, "mem0_write.reason": ""})
        return result

    payload = turn_messages_to_mem0_payload(turn_messages)
    if not payload:
        result = Mem0WriteResult(status="skipped_empty_payload")
        attach_run_metadata({"mem0_write.status": result.status, "mem0_write.reason": ""})
        return result

    try:
        if _memory_add_override is not None:
            raw = _memory_add_override(payload, user_id=uid, infer=True)
        else:
            memory = get_local_memory()
            raw = memory.add(payload, user_id=uid, infer=True)
    except Mem0UserIdError:
        raise
    except Exception as exc:
        result = Mem0WriteResult(status="failed", reason=type(exc).__name__)
        logger.exception(
            "mem0_write.store_failed",
            extra={"user_id": uid, "reason": result.reason},
        )
        attach_run_metadata(
            {
                "mem0_write.status": result.status,
                "mem0_write.reason": result.reason,
                "mem0_write.stored_count": 0,
            }
        )
        return result

    stored = parse_memories_from_get_all(raw)
    result = Mem0WriteResult(status="stored", stored_memories=tuple(stored))
    if stored:
        logger.info(
            "mem0_write.stored",
            extra={"user_id": uid, "count": len(stored)},
        )
    else:
        result = Mem0WriteResult(status="stored_empty")
    attach_run_metadata(
        {
            "mem0_write.status": result.status,
            "mem0_write.reason": result.reason,
            "mem0_write.stored_count": result.stored_count,
        }
    )
    return result


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
    result: Mem0WriteResult,
    extra: dict[str, object],
) -> None:
    attach_run_metadata(
        {
            **extra,
            "mem0_write.status": result.status,
            "mem0_write.reason": result.reason,
            "mem0_write.stored_count": result.stored_count,
        }
    )
