"""Typed Server-Sent Events emitted by the Agent chat gateway."""

from __future__ import annotations

from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

from gateway.schemas import ClientAction


class _SseBase(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TokenSseEvent(_SseBase):
    type: Literal["token"] = "token"
    content: str
    segment_id: str


class DoneSseEvent(_SseBase):
    type: Literal["done"] = "done"


class ClientActionsSseEvent(_SseBase):
    type: Literal["client_actions"] = "client_actions"
    client_actions: list[ClientAction] = Field(default_factory=list)


class RetractSseEvent(_SseBase):
    type: Literal["retract"] = "retract"
    segment_id: str
    reason: str


class ReplaceSseEvent(_SseBase):
    type: Literal["replace"] = "replace"
    segment_id: str
    content: str


class ErrorSseEvent(_SseBase):
    type: Literal["error"] = "error"
    message: str


SseEventType = Literal["token", "done", "client_actions", "retract", "replace", "error"]
SseEvent = Annotated[
    Union[
        TokenSseEvent,
        DoneSseEvent,
        ClientActionsSseEvent,
        RetractSseEvent,
        ReplaceSseEvent,
        ErrorSseEvent,
    ],
    Field(discriminator="type"),
]

_SSE_EVENT_ADAPTER: TypeAdapter[SseEvent] = TypeAdapter(SseEvent)


def validate_sse_event(payload: dict[str, object]) -> SseEvent:
    """Validate an SSE payload without changing the legacy dict wire shape."""
    return _SSE_EVENT_ADAPTER.validate_python(payload)
