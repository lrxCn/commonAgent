"""Paginated thread history from LangGraph checkpoints (read-only, UI replay)."""

from __future__ import annotations

from datetime import datetime, timezone
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from pydantic import ValidationError

from gateway.schemas import ClientAction
from gateway.schemas_history import HistoryMessageItem, HistoryMessagesResponse, HistoryRole
from graph.client_actions import CLIENT_ACTIONS_METADATA_KEY
from memory.history import ThreadIdError, load_thread_messages

DEFAULT_HISTORY_LIMIT = 20
MAX_HISTORY_LIMIT = 100


def _clamp_limit(limit: int | None) -> int:
    if limit is None:
        return DEFAULT_HISTORY_LIMIT
    return max(1, min(int(limit), MAX_HISTORY_LIMIT))


def _message_content_text(message: BaseMessage) -> str:
    content = message.content
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and block.get("type") == "text":
                parts.append(str(block.get("text", "")))
        return "".join(parts)
    return str(content) if content is not None else ""


def _message_role(message: BaseMessage) -> HistoryRole:
    if isinstance(message, HumanMessage):
        return "human"
    if isinstance(message, AIMessage):
        return "ai"
    if isinstance(message, SystemMessage):
        return "system"
    if isinstance(message, ToolMessage):
        return "tool"
    msg_type = getattr(message, "type", None)
    if msg_type in ("human", "ai", "system", "tool"):
        return msg_type  # type: ignore[return-value]
    return "other"


def _message_timestamp(message: BaseMessage) -> str | None:
    for container in (
        getattr(message, "response_metadata", None) or {},
        getattr(message, "additional_kwargs", None) or {},
    ):
        if not isinstance(container, dict):
            continue
        for key in ("timestamp", "created_at", "ts"):
            raw = container.get(key)
            if raw is None:
                continue
            if isinstance(raw, datetime):
                dt = raw if raw.tzinfo else raw.replace(tzinfo=timezone.utc)
                return dt.isoformat()
            text = str(raw).strip()
            if text:
                return text
    return None


def _parse_client_actions(message: BaseMessage) -> list[ClientAction] | None:
    kwargs = getattr(message, "additional_kwargs", None) or {}
    if not isinstance(kwargs, dict):
        return None
    raw = kwargs.get(CLIENT_ACTIONS_METADATA_KEY)
    if not raw:
        return None
    if not isinstance(raw, list):
        return None
    actions: list[ClientAction] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        try:
            actions.append(ClientAction.model_validate(item))
        except ValidationError:
            continue
    return actions or None


def _message_id(message: BaseMessage) -> str | None:
    raw_id = getattr(message, "id", None)
    if raw_id is None:
        return None
    text = str(raw_id).strip()
    return text or None


def message_to_history_item(message: BaseMessage) -> HistoryMessageItem:
    """Map a LangChain checkpoint message to a history API item."""
    return HistoryMessageItem(
        message_id=_message_id(message),
        role=_message_role(message),
        content=_message_content_text(message),
        timestamp=_message_timestamp(message),
        client_actions=_parse_client_actions(message),
    )


def _resolve_start_offset(messages: list[BaseMessage], cursor: str | None) -> int:
    if not cursor or not str(cursor).strip():
        return 0
    token = str(cursor).strip()
    if token.isdigit():
        return min(int(token), len(messages))
    for index, message in enumerate(messages):
        if _message_id(message) == token:
            return min(index + 1, len(messages))
    return 0


def paginate_thread_messages(
    thread_id: str,
    *,
    cursor: str | None = None,
    limit: int | None = None,
) -> HistoryMessagesResponse:
    """Return one page of checkpoint messages for UI display."""
    page_size = _clamp_limit(limit)
    messages = load_thread_messages(thread_id)
    start = _resolve_start_offset(messages, cursor)
    page = messages[start : start + page_size]
    items = [message_to_history_item(message) for message in page]
    next_start = start + len(page)
    next_cursor = str(next_start) if next_start < len(messages) else None
    return HistoryMessagesResponse(items=items, next_cursor=next_cursor)


def list_thread_messages(
    thread_id: str,
    *,
    cursor: str | None = None,
    limit: int | None = None,
) -> HistoryMessagesResponse:
    """Gateway entry: validate thread_id and return paginated history."""
    tid = str(thread_id).strip()
    if not tid:
        raise ThreadIdError("thread_id is required")
    return paginate_thread_messages(tid, cursor=cursor, limit=limit)
