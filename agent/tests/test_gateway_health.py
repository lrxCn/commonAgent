"""Tests for gateway HTTP routes — health and internal chat (SSE)."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from gateway.app import create_app
from settings.config import Settings, reset_settings, set_settings_override
from tests.support.gateway_graph import install_gateway_graph_mocks, teardown_gateway_graph_mocks

_VALID_CHAT_PAYLOAD = {
    "thread_id": "550e8400-e29b-41d4-a716-446655440000",
    "message": "你好",
    "context": {
        "user_id": "user-1",
        "role_id": "role-sales",
        "tools": [],
    },
}

_TEST_SETTINGS = Settings(
    LANGSMITH_API_KEY="lsv2_test",
    OPENAI_API_KEY="sk-test",
    DATABASE_URL="postgresql://postgres:test@localhost:5432/common_agent",
    AGENT_HOST="127.0.0.1",
    AGENT_PORT=18080,
)


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    reset_settings()
    set_settings_override(_TEST_SETTINGS)
    install_gateway_graph_mocks(monkeypatch, settings=_TEST_SETTINGS)
    yield TestClient(create_app())
    teardown_gateway_graph_mocks()


def test_health_returns_200(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "agent-gateway"
    assert body["port"] == 18080


def test_internal_chat_returns_sse_for_valid_json(client: TestClient) -> None:
    response = client.post("/internal/chat", json=_VALID_CHAT_PAYLOAD)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    events = [
        json.loads(line[6:])
        for line in response.text.splitlines()
        if line.startswith("data: ")
    ]
    assert any(event.get("type") == "token" for event in events)
    assert events[-1] == {"type": "done"}


def test_internal_chat_rejects_invalid_json(client: TestClient) -> None:
    invalid = {**_VALID_CHAT_PAYLOAD, "context": {"user_id": "user-1"}}
    response = client.post("/internal/chat", json=invalid)
    assert response.status_code == 422
