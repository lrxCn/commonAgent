"""Tests for client_actions parsing, validation, graph branch, and gateway stub."""

from __future__ import annotations

import json

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.memory import MemorySaver

from gateway.schemas import ChatRequest, ClientAction, RequestContext, ToolSpec
from graph.build import compile_graph
from graph.client_actions import (
    CLIENT_ACTIONS_METADATA_KEY,
    ERROR_PARSE,
    ERROR_TOOL_NOT_ALLOWED,
    build_client_actions_assistant_message,
    parse_client_actions_from_llm,
    validate_client_actions,
)
from graph.context import graph_context_from_request
from graph.supervisor import reset_supervisor_overrides, set_supervisor_invoke
from settings.config import Settings, reset_settings, set_settings_override

_JUMP_TOOL = ToolSpec(
    name="jumpPage",
    description="Navigate to a page.",
    parameters={
        "type": "object",
        "properties": {"page": {"type": "string"}},
        "required": ["page"],
    },
    requires_approval=False,
)

_OTHER_TOOL = ToolSpec(
    name="exportReport",
    description="Export a report.",
    parameters={"type": "object", "properties": {}},
    requires_approval=True,
)

_CREATE_STUDENT_TOOL = ToolSpec(
    name="createStudent",
    description="Open the create-student form.",
    parameters={
        "type": "object",
        "properties": {
            "student_no": {"type": "string"},
            "name": {"type": "string"},
            "class_name": {"type": "string"},
            "status": {"type": "string", "enum": ["active", "inactive"]},
        },
        "required": [],
    },
    requires_approval=True,
)

_REQUIRED_ENV = {
    "LANGSMITH_API_KEY": "lsv2_test",
    "OPENAI_API_KEY": "sk-test",
    "DATABASE_URL": "postgresql://postgres:test@localhost:5432/common_agent",
    "GUARDRAILS_ENABLED": False,
    "MEMORY_STORE_MOCK": True,
    "QDRANT_MOCK": True,
    "RAG_ROUTER_MODE": "rules",
}


def test_parse_valid_client_actions_json() -> None:
    payload = json.dumps(
        {
            "client_actions": [
                {"tool": "jumpPage", "args": {"page": "pageA"}, "requires_approval": True}
            ]
        }
    )
    outcome = parse_client_actions_from_llm(payload, [_JUMP_TOOL])
    assert outcome.kind == "client_actions"
    assert len(outcome.actions) == 1
    action = outcome.actions[0]
    assert action.tool == "jumpPage"
    assert action.args == {"page": "pageA"}
    assert action.requires_approval is False


def test_parse_create_student_with_optional_args() -> None:
    payload = json.dumps(
        {
            "client_actions": [
                {
                    "tool": "createStudent",
                    "args": {"name": "张三", "student_no": "2024004"},
                    "requires_approval": False,
                }
            ]
        }
    )
    outcome = parse_client_actions_from_llm(payload, [_CREATE_STUDENT_TOOL])
    assert outcome.kind == "client_actions"
    assert len(outcome.actions) == 1
    action = outcome.actions[0]
    assert action.tool == "createStudent"
    assert action.args == {"name": "张三", "student_no": "2024004"}
    assert action.requires_approval is True


def test_parse_create_student_empty_args() -> None:
    payload = json.dumps({"client_actions": [{"tool": "createStudent", "args": {}}]})
    outcome = parse_client_actions_from_llm(payload, [_CREATE_STUDENT_TOOL])
    assert outcome.kind == "client_actions"
    assert outcome.actions[0].args == {}


def test_tool_not_in_whitelist_rejected() -> None:
    payload = json.dumps(
        {"client_actions": [{"tool": "unknownTool", "args": {}, "requires_approval": False}]}
    )
    outcome = parse_client_actions_from_llm(payload, [_JUMP_TOOL])
    assert outcome.kind == "error"
    assert outcome.error_code == ERROR_TOOL_NOT_ALLOWED


def test_parse_failure_returns_error_code() -> None:
    outcome = parse_client_actions_from_llm('{"client_actions": [invalid', [_JUMP_TOOL])
    assert outcome.kind == "error"
    assert outcome.error_code == ERROR_PARSE


def test_validate_empty_whitelist_rejects() -> None:
    outcome = validate_client_actions(
        [{"tool": "jumpPage", "args": {"page": "pageA"}}],
        [],
    )
    assert outcome.kind == "error"
    assert outcome.error_code == ERROR_TOOL_NOT_ALLOWED


def test_build_assistant_message_metadata() -> None:
    action = ClientAction(tool="jumpPage", args={"page": "pageA"}, requires_approval=False)
    message = build_client_actions_assistant_message([action])
    assert message.content == ""
    assert CLIENT_ACTIONS_METADATA_KEY in message.additional_kwargs
    stored = message.additional_kwargs[CLIENT_ACTIONS_METADATA_KEY]
    assert stored[0]["tool"] == "jumpPage"
    assert stored[0]["args"] == {"page": "pageA"}


def test_graph_skips_outbound_guard_for_client_actions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("graph.nodes.load_thread_messages", lambda _thread_id: [])
    monkeypatch.setattr("graph.nodes.get_rolling_summary", lambda _thread_id: None)
    monkeypatch.setattr("graph.nodes.schedule_post_turn_jobs", lambda **_kwargs: None)

    reset_settings()
    set_settings_override(Settings(**_REQUIRED_ENV))  # type: ignore[arg-type]
    reset_supervisor_overrides()

    json_reply = json.dumps(
        {"client_actions": [{"tool": "jumpPage", "args": {"page": "pageA"}}]}
    )

    set_supervisor_invoke(lambda _system, _messages: [AIMessage(content=json_reply)])

    graph = compile_graph(checkpointer=MemorySaver(), use_pooled_postgres=False)
    ctx = graph_context_from_request(
        RequestContext(user_id="u1", role_id="r1", tools=[_JUMP_TOOL])
    )
    result = graph.invoke(
        {"messages": [HumanMessage(content="跳转到页面 A")]},
        context=ctx,
        config={"configurable": {"thread_id": "thread-ca-1"}},
    )

    actions = result.get("client_actions") or []
    assert len(actions) == 1
    assert actions[0].tool == "jumpPage"

    ai_messages = [m for m in result.get("messages") or [] if isinstance(m, AIMessage)]
    assert ai_messages
    last_ai = ai_messages[-1]
    assert last_ai.additional_kwargs.get(CLIENT_ACTIONS_METADATA_KEY)
    assert not str(last_ai.content).strip()

    reset_supervisor_overrides()
    reset_settings()


def test_gateway_returns_client_actions_json(monkeypatch: pytest.MonkeyPatch) -> None:
    from fastapi.testclient import TestClient

    from gateway.app import create_app
    from tests.support.gateway_graph import install_gateway_graph_mocks, teardown_gateway_graph_mocks

    json_reply = json.dumps(
        {"client_actions": [{"tool": "jumpPage", "args": {"page": "pageA"}}]}
    )
    install_gateway_graph_mocks(monkeypatch, supervisor_reply=json_reply)
    client = TestClient(create_app())
    payload = {
        "thread_id": "550e8400-e29b-41d4-a716-446655440000",
        "message": "请跳转到页面 A",
        "context": {
            "user_id": "user-1",
            "role_id": "role-sales",
            "tools": [_JUMP_TOOL.model_dump()],
        },
    }
    response = client.post("/internal/chat", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body.get("text") is None
    assert body.get("client_actions") == [
        {
            "tool": "jumpPage",
            "args": {"page": "pageA"},
            "requires_approval": False,
        }
    ]
    teardown_gateway_graph_mocks()


def test_gateway_plain_message_returns_sse(monkeypatch: pytest.MonkeyPatch) -> None:
    from fastapi.testclient import TestClient

    from gateway.app import create_app
    from tests.support.gateway_graph import install_gateway_graph_mocks, teardown_gateway_graph_mocks

    install_gateway_graph_mocks(monkeypatch)
    client = TestClient(create_app())
    req = ChatRequest(
        thread_id="550e8400-e29b-41d4-a716-446655440000",
        message="你好",
        context=RequestContext(user_id="u1", role_id="r1", tools=[_OTHER_TOOL]),
    )
    response = client.post("/internal/chat", json=req.model_dump())
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    teardown_gateway_graph_mocks()
