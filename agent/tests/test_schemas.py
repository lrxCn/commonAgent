"""Tests for gateway.schemas — chat request/response Pydantic models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from gateway.schemas import ChatRequest, ChatResponse, ClientAction, RequestContext, ToolSpec

_VALID_CHAT_PAYLOAD = {
    "thread_id": "550e8400-e29b-41d4-a716-446655440000",
    "message": "请跳转到页面 A",
    "context": {
        "user_id": "user-1",
        "role_ids": ["role-sales"],
        "tools": [
            {
                "name": "jumpPage",
                "description": "Navigate to a page in the app.",
                "parameters": {
                    "type": "object",
                    "properties": {"page": {"type": "string"}},
                    "required": ["page"],
                },
                "requires_approval": True,
            }
        ],
    },
}


def test_valid_chat_request_parses() -> None:
    req = ChatRequest.model_validate(_VALID_CHAT_PAYLOAD)
    assert req.thread_id == _VALID_CHAT_PAYLOAD["thread_id"]
    assert req.message == "请跳转到页面 A"
    assert req.context.user_id == "user-1"
    assert req.context.role_ids == ["role-sales"]
    assert len(req.context.tools) == 1
    assert req.context.tools[0].name == "jumpPage"
    assert req.context.tools[0].requires_approval is True


def test_context_tools_default_empty() -> None:
    ctx = RequestContext.model_validate({"user_id": "u1", "role_ids": ["r1"]})
    assert ctx.tools == []


def test_missing_context_role_ids_fails() -> None:
    payload = {
        **_VALID_CHAT_PAYLOAD,
        "context": {"user_id": "user-1"},
    }
    with pytest.raises(ValidationError) as exc_info:
        ChatRequest.model_validate(payload)
    errors = exc_info.value.errors()
    assert any(e["loc"] == ("context", "role_ids") for e in errors)


def test_deprecated_role_id_alias_still_parses() -> None:
    payload = {
        **_VALID_CHAT_PAYLOAD,
        "context": {"user_id": "user-1", "role_id": "role-hr", "tools": []},
    }
    req = ChatRequest.model_validate(payload)
    assert req.context.role_ids == ["role-hr"]
    assert req.context.role_id == "role-hr"


def test_empty_thread_id_fails() -> None:
    payload = {**_VALID_CHAT_PAYLOAD, "thread_id": "   "}
    with pytest.raises(ValidationError):
        ChatRequest.model_validate(payload)


def test_tool_spec_requires_approval() -> None:
    tool = ToolSpec.model_validate(
        {
            "name": "jumpPage",
            "description": "Jump",
            "parameters": {"type": "object"},
            "requires_approval": True,
        }
    )
    assert tool.requires_approval is True


def test_client_action_and_chat_response_round_trip() -> None:
    action = ClientAction.model_validate(
        {"tool": "jumpPage", "args": {"page": "pageA"}, "requires_approval": False}
    )
    response = ChatResponse.model_validate(
        {"text": None, "client_actions": [action.model_dump()]}
    )
    assert response.text is None
    assert response.client_actions is not None
    assert response.client_actions[0].tool == "jumpPage"
    assert response.client_actions[0].args == {"page": "pageA"}
