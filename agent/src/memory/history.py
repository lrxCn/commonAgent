"""Read conversation history and rolling summary from LangGraph Postgres checkpoints."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from langchain_core.messages import BaseMessage, HumanMessage, messages_from_dict
from langgraph.checkpoint.base import CheckpointTuple
from langgraph.checkpoint.postgres import PostgresSaver

from memory.checkpointer import get_pooled_checkpointer

ROLLING_SUMMARY_METADATA_KEY = "rolling_summary"

_checkpointer_override: PostgresSaver | None = None


class ThreadIdError(ValueError):
    """Raised when thread_id is missing or blank for checkpoint reads."""


def set_history_checkpointer(checkpointer: PostgresSaver | None) -> None:
    """Replace checkpointer used by history helpers (tests)."""
    global _checkpointer_override
    _checkpointer_override = checkpointer


def _require_thread_id(thread_id: str | None) -> str:
    if thread_id is None or not str(thread_id).strip():
        raise ThreadIdError("thread_id is required to load checkpoint history")
    return str(thread_id).strip()


def _thread_config(thread_id: str) -> dict[str, Any]:
    return {"configurable": {"thread_id": thread_id}}


def _resolve_checkpointer() -> PostgresSaver:
    if _checkpointer_override is not None:
        return _checkpointer_override
    return get_pooled_checkpointer(setup=False)


def _get_latest_checkpoint_tuple(thread_id: str) -> CheckpointTuple | None:
    checkpointer = _resolve_checkpointer()
    return checkpointer.get_tuple(_thread_config(thread_id))


def _normalize_messages(raw: Any) -> list[BaseMessage]:
    if not raw:
        return []
    if not isinstance(raw, list):
        return []
    if isinstance(raw[0], BaseMessage):
        return list(raw)
    return messages_from_dict(raw)


def load_thread_messages(thread_id: str) -> list[BaseMessage]:
    """Load the latest message list for a thread from the checkpointer."""
    tid = _require_thread_id(thread_id)
    checkpoint_tuple = _get_latest_checkpoint_tuple(tid)
    if checkpoint_tuple is None:
        return []

    channel_values = checkpoint_tuple.checkpoint.get("channel_values") or {}
    return _normalize_messages(channel_values.get("messages"))


def get_rolling_summary(thread_id: str) -> str | None:
    """Return rolling summary stored in checkpoint metadata, if present."""
    tid = _require_thread_id(thread_id)
    checkpoint_tuple = _get_latest_checkpoint_tuple(tid)
    if checkpoint_tuple is None:
        return None

    metadata = checkpoint_tuple.metadata or {}
    summary = metadata.get(ROLLING_SUMMARY_METADATA_KEY)
    if summary is None:
        channel_values = checkpoint_tuple.checkpoint.get("channel_values") or {}
        summary = channel_values.get(ROLLING_SUMMARY_METADATA_KEY)

    if summary is None:
        return None
    text = str(summary).strip()
    return text or None


def count_turns(messages: Sequence[BaseMessage]) -> int:
    """Count user-initiated turns (human messages) in a message list."""
    return sum(1 for message in messages if isinstance(message, HumanMessage))
