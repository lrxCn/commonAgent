"""Pydantic models for history pagination API (see root README API contract)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from gateway.schemas import ClientAction


HistoryRole = Literal["human", "ai", "system", "tool", "other"]


class HistoryMessageItem(BaseModel):
    """One checkpoint message for UI replay (read-only; not used for model inference)."""

    message_id: str | None = Field(
        default=None,
        description="Stable message id when present in checkpoint; usable as cursor.",
    )
    role: HistoryRole = Field(..., description="Message role for display.")
    content: str = Field(..., description="Text content for display.")
    timestamp: str | None = Field(
        default=None,
        description="ISO-8601 timestamp when available on the message or checkpoint.",
    )
    client_actions: list[ClientAction] | None = Field(
        default=None,
        description="External tool invocations stored on assistant messages.",
    )


class HistoryMessagesResponse(BaseModel):
    """Paginated thread history from the checkpointer."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "items": [
                        {
                            "message_id": "msg-1",
                            "role": "human",
                            "content": "你好",
                            "timestamp": "2026-05-19T12:00:00+00:00",
                            "client_actions": None,
                        }
                    ],
                    "next_cursor": "1",
                }
            ]
        }
    )

    items: list[HistoryMessageItem] = Field(
        default_factory=list,
        description="Page of messages in checkpoint order.",
    )
    next_cursor: str | None = Field(
        default=None,
        description="Pass as cursor to fetch the next page; null when no more items.",
    )
