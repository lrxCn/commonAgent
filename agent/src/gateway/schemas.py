"""Pydantic models for Gateway chat request/response (see root README API contract)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ToolSpec(BaseModel):
    """External tool definition supplied per request; not persisted in checkpoint state."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "name": "jumpPage",
                    "description": "Navigate the user to an in-app page.",
                    "parameters": {
                        "type": "object",
                        "properties": {"page": {"type": "string"}},
                        "required": ["page"],
                    },
                    "requires_approval": True,
                }
            ]
        }
    )

    name: str = Field(..., min_length=1, description="Tool name registered for this role.")
    description: str = Field(..., description="Human-readable tool description for the LLM.")
    parameters: dict[str, Any] = Field(
        default_factory=dict,
        description="JSON Schema object describing tool arguments.",
    )
    requires_approval: bool = Field(
        default=False,
        description="When true, the client must confirm before executing the tool.",
    )


class RequestContext(BaseModel):
    """Per-turn identity and tool whitelist; passed on each chat request, not checkpoint state."""

    user_id: str = Field(..., min_length=1, description="Authenticated user identifier from Back.")
    role_id: str = Field(..., min_length=1, description="Role used for RAG filtering and tool whitelist.")
    tools: list[ToolSpec] = Field(
        default_factory=list,
        description="External tools the model may emit as client_actions this turn.",
    )


class ChatRequest(BaseModel):
    """Inbound body for POST /internal/chat."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "thread_id": "550e8400-e29b-41d4-a716-446655440000",
                    "message": "请跳转到页面 A",
                    "context": {
                        "user_id": "user-1",
                        "role_id": "role-sales",
                        "tools": [
                            {
                                "name": "jumpPage",
                                "description": "Navigate to a page in the app.",
                                "parameters": {
                                    "type": "object",
                                    "properties": {"page": {"type": "string"}},
                                    "required": ["page"],
                                },
                                "requires_approval": False,
                            }
                        ],
                    },
                }
            ]
        }
    )

    thread_id: str = Field(..., description="Conversation thread id (LangGraph checkpoint key).")
    message: str = Field(..., description="User message for this turn.")
    context: RequestContext = Field(..., description="Per-request user, role, and external tools.")

    @field_validator("thread_id")
    @classmethod
    def thread_id_non_empty(cls, value: str) -> str:
        if not value or not value.strip():
            msg = "thread_id must be a non-empty string"
            raise ValueError(msg)
        return value.strip()


class ClientAction(BaseModel):
    """Structured external tool invocation for the client to execute (see root README)."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "tool": "jumpPage",
                    "args": {"page": "pageA"},
                    "requires_approval": False,
                }
            ]
        }
    )

    tool: str = Field(..., min_length=1, description="Tool name; must appear in request context.tools.")
    args: dict[str, Any] = Field(
        default_factory=dict,
        description="Arguments for the tool, shaped by the tool JSON Schema.",
    )
    requires_approval: bool = Field(
        default=False,
        description="When true, the client must show a confirmation UI before executing.",
    )


class ChatResponse(BaseModel):
    """JSON chat completion payload (non-SSE); may include client_actions instead of or with text."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "text": "好的，正在为您跳转。",
                    "client_actions": None,
                },
                {
                    "text": None,
                    "client_actions": [
                        {
                            "tool": "jumpPage",
                            "args": {"page": "pageA"},
                            "requires_approval": False,
                        }
                    ],
                },
            ]
        }
    )

    text: str | None = Field(
        default=None,
        description="Assistant reply text when the turn is answered in natural language.",
    )
    client_actions: list[ClientAction] | None = Field(
        default=None,
        description="External tools for the client to execute; ends the turn without server execution.",
    )
