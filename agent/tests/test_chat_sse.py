"""Gateway chat: SSE text stream and client_actions JSON via mocked graph."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient
from gateway.app import create_app
from guardrails.inbound import INJECTION_TEST_SAMPLE
from guardrails.outbound import OUTBOUND_SAFE_REPLY, OUTBOUND_TEST_SAMPLE
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
    token_events = [event for event in events if event.get("type") == "token"]
    assert len(token_events) >= 1
    assert any("mock-reply" in event.get("content", "") for event in token_events)
    assert events[-1] == {"type": "done"}

    combined = "".join(event["content"] for event in token_events)
    assert combined == "mock-reply:你好"


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

    response = guarded.post("/internal/chat", json=_VALID_CHAT_PAYLOAD)
    assert response.status_code == 200
    events = _parse_sse_events(response.text)
    combined = "".join(event["content"] for event in events if event.get("type") == "token")
    assert OUTBOUND_SAFE_REPLY in combined
    teardown_gateway_graph_mocks()


def test_format_sse_event_roundtrip() -> None:
    from gateway.chat import format_sse_event

    frame = format_sse_event({"type": "token", "content": "hi"})
    assert frame == 'data: {"type": "token", "content": "hi"}\n\n'
