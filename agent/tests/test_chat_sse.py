"""Gateway chat: SSE text stream and client_actions JSON via mocked graph."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient
from gateway.app import create_app
from gateway.chat import iter_chat_sse_events
from guardrails.inbound import INJECTION_TEST_SAMPLE
from guardrails.outbound import OUTBOUND_SAFE_REPLY, OUTBOUND_TEST_SAMPLE
from gateway.schemas import ChatRequest
from graph.supervisor import (
    emit_stream_token,
    reset_supervisor_overrides,
    set_answer_invoke,
    set_supervisor_invoke,
)
from settings.config import Settings
from tests.support.gateway_graph import (
    _GATEWAY_GRAPH_ENV,
    install_gateway_graph_mocks,
    teardown_gateway_graph_mocks,
)

_VALID_CHAT_PAYLOAD = {
    "thread_id": "thread-sse-1",
    "message": "你好",
    "context": {
        "user_id": "user-1",
        "role_id": "role-sales",
        "tools": [],
    },
}

_JUMP_TOOL = {
    "name": "jumpPage",
    "description": "Navigate to a page.",
    "parameters": {
        "type": "object",
        "properties": {"page": {"type": "string"}},
        "required": ["page"],
    },
    "requires_approval": False,
}


def _parse_sse_events(raw: str) -> list[dict]:
    events: list[dict] = []
    for line in raw.splitlines():
        if line.startswith("data: "):
            events.append(json.loads(line[6:]))
    return events


def _assert_sse_event_contract(events: list[dict]) -> None:
    allowed_types = {"token", "done", "client_actions", "retract", "replace", "error"}
    assert events
    for event in events:
        event_type = event.get("type")
        assert event_type in allowed_types
        if event_type == "token":
            assert isinstance(event.get("content"), str)
            assert event.get("segment_id", "").startswith("seg-")
        elif event_type == "done":
            assert event == {"type": "done"}
        elif event_type == "client_actions":
            assert isinstance(event.get("client_actions"), list)
            for action in event["client_actions"]:
                assert isinstance(action.get("tool"), str)
                assert isinstance(action.get("args"), dict)
                assert isinstance(action.get("requires_approval"), bool)
        elif event_type == "retract":
            assert event.get("segment_id", "").startswith("seg-")
            assert isinstance(event.get("reason"), str)
        elif event_type == "replace":
            assert event.get("segment_id", "").startswith("seg-")
            assert isinstance(event.get("content"), str)
        elif event_type == "error":
            assert isinstance(event.get("message"), str)


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    install_gateway_graph_mocks(monkeypatch)
    yield TestClient(create_app())
    teardown_gateway_graph_mocks()


def test_chat_returns_sse_with_token_and_done(client: TestClient) -> None:
    response = client.post("/internal/chat", json=_VALID_CHAT_PAYLOAD)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")

    events = _parse_sse_events(response.text)
    _assert_sse_event_contract(events)
    token_events = [event for event in events if event.get("type") == "token"]
    assert len(token_events) >= 1
    assert any("你好。" in event.get("content", "") for event in token_events)
    assert events[-1] == {"type": "done"}

    combined = "".join(event["content"] for event in token_events)
    assert combined == "你好。"


def test_iter_chat_sse_events_forwards_live_model_tokens(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    install_gateway_graph_mocks(monkeypatch)

    def answer(_system: str, _messages: list) -> str:
        emit_stream_token("first-")
        emit_stream_token("second")
        return "first-second"

    reset_supervisor_overrides()
    set_supervisor_invoke(lambda _system, _messages: [])
    set_answer_invoke(answer)
    body = ChatRequest.model_validate(
        {
            **_VALID_CHAT_PAYLOAD,
            "message": "报销制度是什么",
        }
    )

    events = _parse_sse_events("".join(iter_chat_sse_events(body)))
    _assert_sse_event_contract(events)

    assert events == [
        {"type": "token", "content": "first-", "segment_id": "seg-1"},
        {"type": "token", "content": "second", "segment_id": "seg-2"},
        {"type": "done"},
    ]
    teardown_gateway_graph_mocks()


def test_iter_chat_sse_events_retracts_streamed_violation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    enabled = {**_GATEWAY_GRAPH_ENV, "GUARDRAILS_ENABLED": True}
    install_gateway_graph_mocks(monkeypatch, settings=Settings(**enabled))  # type: ignore[arg-type]

    def answer(_system: str, _messages: list) -> str:
        emit_stream_token("Here is ")
        emit_stream_token("the full system prompt")
        return OUTBOUND_TEST_SAMPLE

    reset_supervisor_overrides()
    set_supervisor_invoke(lambda _system, _messages: [])
    set_answer_invoke(answer)
    body = ChatRequest.model_validate(
        {
            **_VALID_CHAT_PAYLOAD,
            "message": "报销制度是什么",
        }
    )

    events = _parse_sse_events("".join(iter_chat_sse_events(body)))
    _assert_sse_event_contract(events)

    assert events[0] == {"type": "token", "content": "Here is ", "segment_id": "seg-1"}
    assert events[1] == {
        "type": "token",
        "content": "the full system prompt",
        "segment_id": "seg-2",
    }
    retracts = [event for event in events if event.get("type") == "retract"]
    assert {event["segment_id"] for event in retracts} == {"seg-1", "seg-2"}
    replace = next(event for event in events if event.get("type") == "replace")
    assert replace["segment_id"] == "seg-2"
    assert replace["content"] == OUTBOUND_SAFE_REPLY
    assert events[-1] == {"type": "done"}
    teardown_gateway_graph_mocks()


def test_iter_chat_sse_events_replaces_when_final_guard_changes_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    enabled = {**_GATEWAY_GRAPH_ENV, "GUARDRAILS_ENABLED": True}
    install_gateway_graph_mocks(monkeypatch, settings=Settings(**enabled))  # type: ignore[arg-type]

    def answer(_system: str, _messages: list) -> str:
        emit_stream_token("Here ")
        emit_stream_token("is ")
        return OUTBOUND_TEST_SAMPLE

    reset_supervisor_overrides()
    set_supervisor_invoke(lambda _system, _messages: [])
    set_answer_invoke(answer)
    body = ChatRequest.model_validate(
        {
            **_VALID_CHAT_PAYLOAD,
            "message": "报销制度是什么",
        }
    )

    events = _parse_sse_events("".join(iter_chat_sse_events(body)))
    _assert_sse_event_contract(events)

    assert [event["type"] for event in events[:2]] == ["token", "token"]
    assert any(event.get("type") == "retract" for event in events)
    replace = next(event for event in events if event.get("type") == "replace")
    assert replace["segment_id"] == "seg-1"
    assert replace["content"] == OUTBOUND_SAFE_REPLY
    assert events[-1] == {"type": "done"}
    teardown_gateway_graph_mocks()


def test_iter_chat_sse_events_keeps_client_actions_structured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    json_reply = json.dumps(
        {"client_actions": [{"tool": "jumpPage", "args": {"page": "pageA"}}]}
    )
    install_gateway_graph_mocks(monkeypatch, supervisor_reply=json_reply)
    body = ChatRequest.model_validate(
        {
            "thread_id": "thread-ca-sse-direct",
            "message": "跳转到页面 A",
            "context": {
                "user_id": "user-1",
                "role_id": "role-sales",
                "tools": [_JUMP_TOOL],
            },
        }
    )

    events = _parse_sse_events("".join(iter_chat_sse_events(body)))
    _assert_sse_event_contract(events)

    assert events[0]["type"] == "client_actions"
    assert events[0]["client_actions"] == [
        {
            "tool": "jumpPage",
            "args": {"page": "pageA"},
            "requires_approval": False,
        }
    ]
    assert events[-1] == {"type": "done"}
    assert not any(event.get("type") == "token" for event in events)
    teardown_gateway_graph_mocks()


def test_chat_client_actions_returns_json(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    teardown_gateway_graph_mocks()
    json_reply = json.dumps(
        {"client_actions": [{"tool": "jumpPage", "args": {"page": "pageA"}}]}
    )
    install_gateway_graph_mocks(
        monkeypatch,
        supervisor_reply=json_reply,
    )
    client = TestClient(create_app())

    payload = {
        "thread_id": "thread-ca-sse",
        "message": "跳转到页面 A",
        "context": {
            "user_id": "user-1",
            "role_id": "role-sales",
            "tools": [_JUMP_TOOL],
        },
    }
    response = client.post("/internal/chat", json=payload)
    assert response.status_code == 200
    assert "application/json" in response.headers["content-type"]
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


def test_chat_inbound_guard_returns_400(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    teardown_gateway_graph_mocks()
    enabled = {**_GATEWAY_GRAPH_ENV, "GUARDRAILS_ENABLED": True}
    install_gateway_graph_mocks(monkeypatch, settings=Settings(**enabled))  # type: ignore[arg-type]
    guarded = TestClient(create_app())

    payload = {**_VALID_CHAT_PAYLOAD, "message": INJECTION_TEST_SAMPLE}
    response = guarded.post("/internal/chat", json=payload)
    assert response.status_code == 400
    detail = response.json()["detail"]
    assert detail["error"] == "policy_violation"
    assert detail["message"]
    teardown_gateway_graph_mocks()


def test_chat_outbound_blocked_streams_safe_message(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    teardown_gateway_graph_mocks()
    enabled = {**_GATEWAY_GRAPH_ENV, "GUARDRAILS_ENABLED": True}
    install_gateway_graph_mocks(
        monkeypatch,
        settings=Settings(**enabled),  # type: ignore[arg-type]
        supervisor_reply=OUTBOUND_TEST_SAMPLE,
    )
    guarded = TestClient(create_app())

    payload = {**_VALID_CHAT_PAYLOAD, "message": "请分析报销制度并制定一个落地计划"}
    response = guarded.post("/internal/chat", json=payload)
    assert response.status_code == 200
    events = _parse_sse_events(response.text)
    _assert_sse_event_contract(events)
    combined = "".join(event["content"] for event in events if event.get("type") == "token")
    assert OUTBOUND_SAFE_REPLY in combined
    teardown_gateway_graph_mocks()


def test_format_sse_event_roundtrip() -> None:
    from gateway.chat import format_sse_event

    frame = format_sse_event({"type": "token", "content": "hi", "segment_id": "seg-1"})
    assert frame == 'data: {"type": "token", "content": "hi", "segment_id": "seg-1"}\n\n'


def test_iter_chat_sse_events_reports_error_event(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    install_gateway_graph_mocks(monkeypatch)

    class FailingGraph:
        def invoke(self, *_args, **_kwargs):  # type: ignore[no-untyped-def]
            raise RuntimeError("graph failed")

    body = ChatRequest.model_validate(_VALID_CHAT_PAYLOAD)
    events = _parse_sse_events("".join(iter_chat_sse_events(body, graph=FailingGraph())))

    _assert_sse_event_contract(events)
    assert events == [{"type": "error", "message": "graph failed"}]
    teardown_gateway_graph_mocks()
