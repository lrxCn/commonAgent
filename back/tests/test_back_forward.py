"""Back → Agent forwarding and demo context injection."""

from __future__ import annotations

import json

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from api.app import create_app
from services.context import build_agent_chat_payload, build_request_context
from settings.config import Settings, set_settings_override


@pytest.fixture
def test_settings(tmp_path, monkeypatch: pytest.MonkeyPatch) -> Settings:
    tools_file = tmp_path / "tools.json"
    tools_file.write_text(
        json.dumps(
            {
                "tools": [
                    {
                        "name": "jumpPage",
                        "description": "Go to page",
                        "parameters": {"type": "object", "properties": {"page": {"type": "string"}}},
                        "requires_approval": False,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    settings = Settings(
        AGENT_URL="http://agent.test",
        DEMO_USER_ID="demo",
        DEMO_ROLE_ID="demo",
        DEMO_TOOLS_FILE=str(tools_file),
        INTERNAL_API_KEY="test-internal-key",
    )
    set_settings_override(settings)
    monkeypatch.chdir(tmp_path)
    yield settings
    set_settings_override(None)


@pytest.fixture
def client(test_settings: Settings) -> TestClient:
    _ = test_settings
    return TestClient(create_app())


def test_build_request_context_injects_demo_user(test_settings: Settings) -> None:
    ctx = build_request_context(test_settings)
    assert ctx["user_id"] == "demo"
    assert ctx["role_id"] == "demo"
    assert len(ctx["tools"]) == 1
    assert ctx["tools"][0]["name"] == "jumpPage"


def test_build_agent_payload_includes_full_context(test_settings: Settings) -> None:
    payload = build_agent_chat_payload(
        thread_id="t1",
        message="hello",
        settings=test_settings,
    )
    assert payload["thread_id"] == "t1"
    assert payload["message"] == "hello"
    assert payload["context"]["user_id"] == "demo"
    assert payload["context"]["role_id"] == "demo"
    assert payload["context"]["tools"]


@respx.mock
def test_api_chat_forwards_sse(client: TestClient, test_settings: Settings) -> None:
    route = respx.post(f"{test_settings.AGENT_URL}/internal/chat").mock(
        return_value=httpx.Response(
            200,
            headers={"content-type": "text/event-stream"},
            content=b'data: {"type":"token","content":"hi"}\n\ndata: {"type":"done"}\n\n',
        )
    )

    response = client.post(
        "/api/chat",
        json={"thread_id": "t1", "message": "hello"},
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "token" in response.text
    assert route.called
    request = route.calls[0].request
    assert request.headers["x-internal-key"] == "test-internal-key"
    body = json.loads(request.content.decode())
    assert body["context"]["user_id"] == "demo"
    assert body["context"]["role_id"] == "demo"
    assert body["context"]["tools"][0]["name"] == "jumpPage"


@respx.mock
def test_api_chat_forwards_json_client_actions(client: TestClient, test_settings: Settings) -> None:
    agent_body = {
        "text": None,
        "client_actions": [{"tool": "jumpPage", "args": {"page": "pageA"}, "requires_approval": False}],
    }
    respx.post(f"{test_settings.AGENT_URL}/internal/chat").mock(
        return_value=httpx.Response(
            200,
            headers={"content-type": "application/json"},
            json=agent_body,
        )
    )

    response = client.post(
        "/api/chat",
        json={"thread_id": "t2", "message": "打开 pageA"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["client_actions"][0]["tool"] == "jumpPage"


@respx.mock
def test_api_chat_propagates_agent_error(client: TestClient, test_settings: Settings) -> None:
    respx.post(f"{test_settings.AGENT_URL}/internal/chat").mock(
        return_value=httpx.Response(400, json={"detail": "blocked"}),
    )

    response = client.post(
        "/api/chat",
        json={"thread_id": "t1", "message": "bad"},
    )

    assert response.status_code == 400


def test_health(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["service"] == "common-agent-back"
