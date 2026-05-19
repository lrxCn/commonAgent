"""Read conversation history and rolling summary from LangGraph Postgres checkpoints."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from langchain_core.messages import BaseMessage, HumanMessage, messages_from_dict
from langgraph.checkpoint.base import CheckpointTuple
from langgraph.checkpoint.postgres import PostgresSaver

from memory.checkpointer import get_pooled_checkpointer

ROLLING_SUMMARY_METADATA_KEY = "rolling_summary"
ROLLING_SUMMARY_THROUGH_TURN_KEY = "rolling_summary_through_turn"

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


def _summary_from_checkpoint_tuple(checkpoint_tuple: CheckpointTuple) -> tuple[str | None, int | None]:
    metadata = checkpoint_tuple.metadata or {}
    summary = metadata.get(ROLLING_SUMMARY_METADATA_KEY)
    through = metadata.get(ROLLING_SUMMARY_THROUGH_TURN_KEY)
    if summary is None or through is None:
        channel_values = checkpoint_tuple.checkpoint.get("channel_values") or {}
        if summary is None:
            summary = channel_values.get(ROLLING_SUMMARY_METADATA_KEY)
        if through is None:
            through = channel_values.get(ROLLING_SUMMARY_THROUGH_TURN_KEY)

    summary_text: str | None = None
    if summary is not None:
        text = str(summary).strip()
        summary_text = text or None

    through_turn: int | None = None
    if through is not None:
        try:
            through_turn = int(through)
        except (TypeError, ValueError):
            through_turn = None
    return summary_text, through_turn


def get_rolling_summary(thread_id: str) -> str | None:
    """Return rolling summary stored in checkpoint metadata, if present."""
    tid = _require_thread_id(thread_id)
    checkpoint_tuple = _get_latest_checkpoint_tuple(tid)
    if checkpoint_tuple is None:
        return None
    summary, _ = _summary_from_checkpoint_tuple(checkpoint_tuple)
    return summary


def get_rolling_summary_state(thread_id: str) -> tuple[str | None, int | None]:
    """Return rolling summary text and exclusive through-turn index, if stored."""
    tid = _require_thread_id(thread_id)
    checkpoint_tuple = _get_latest_checkpoint_tuple(tid)
    if checkpoint_tuple is None:
        return None, None
    return _summary_from_checkpoint_tuple(checkpoint_tuple)


def save_rolling_summary(thread_id: str, summary: str, *, through_turn: int) -> None:
    """Persist rolling summary and the exclusive turn index covered in checkpoint metadata."""
    tid = _require_thread_id(thread_id)
    checkpoint_tuple = _get_latest_checkpoint_tuple(tid)
    if checkpoint_tuple is None:
        return

    enriched_metadata = {
        **(checkpoint_tuple.metadata or {}),
        ROLLING_SUMMARY_METADATA_KEY: summary.strip(),
        ROLLING_SUMMARY_THROUGH_TURN_KEY: through_turn,
    }
    checkpointer = _resolve_checkpointer()
    checkpointer.put(
        checkpoint_tuple.config,
        checkpoint_tuple.checkpoint,
        enriched_metadata,  # type: ignore[arg-type]
        checkpoint_tuple.checkpoint["channel_versions"],
    )


def count_turns(messages: Sequence[BaseMessage]) -> int:
    """Count user-initiated turns (human messages) in a message list."""
    return sum(1 for message in messages if isinstance(message, HumanMessage))
