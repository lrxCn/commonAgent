"""Tests for GET /internal/threads/{thread_id}/messages history pagination."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.postgres import PostgresSaver

from gateway.app import create_app
from graph.client_actions import CLIENT_ACTIONS_METADATA_KEY
from memory.history import set_history_checkpointer
from settings.config import Settings, reset_settings, set_settings_override
from tests.test_history import _checkpoint_tuple

_TEST_SETTINGS = Settings(
    LANGSMITH_API_KEY="lsv2_test",
    OPENAI_API_KEY="sk-test",
    DATABASE_URL="postgresql://postgres:test@localhost:5432/common_agent",
    AGENT_HOST="127.0.0.1",
    AGENT_PORT=18080,
)


def _build_messages(count: int) -> list[HumanMessage | AIMessage]:
    messages: list[HumanMessage | AIMessage] = []
    for index in range(count):
        if index % 2 == 0:
            messages.append(
                HumanMessage(content=f"msg-{index}", id=f"msg-{index}")
            )
        else:
            messages.append(AIMessage(content=f"msg-{index}", id=f"msg-{index}"))
    return messages


@pytest.fixture
def client() -> TestClient:
    reset_settings()
    set_settings_override(_TEST_SETTINGS)
    yield TestClient(create_app())
    set_history_checkpointer(None)
    reset_settings()


def test_empty_thread_returns_empty_items(client: TestClient) -> None:
    mock_cp = MagicMock(spec=PostgresSaver)
    mock_cp.get_tuple.return_value = None
    set_history_checkpointer(mock_cp)

    response = client.get("/internal/threads/thread-empty/messages")
    assert response.status_code == 200
    body = response.json()
    assert body == {"items": [], "next_cursor": None}


def test_pagination_two_pages_no_duplicate_items(client: TestClient) -> None:
    messages = _build_messages(25)
    mock_cp = MagicMock(spec=PostgresSaver)
    mock_cp.get_tuple.return_value = _checkpoint_tuple(messages=messages)
    set_history_checkpointer(mock_cp)

    page1 = client.get(
        "/internal/threads/thread-paginated/messages",
        params={"limit": 10},
    )
    assert page1.status_code == 200
    body1 = page1.json()
    assert len(body1["items"]) == 10
    assert body1["next_cursor"] == "10"

    page2 = client.get(
        "/internal/threads/thread-paginated/messages",
        params={"cursor": body1["next_cursor"], "limit": 10},
    )
    assert page2.status_code == 200
    body2 = page2.json()
    assert len(body2["items"]) == 10

    ids_page1 = {item.get("message_id") for item in body1["items"]}
    ids_page2 = {item.get("message_id") for item in body2["items"]}
    assert ids_page1.isdisjoint(ids_page2)

    combined = [item["content"] for item in body1["items"] + body2["items"]]
    assert combined[:4] == ["msg-0", "msg-1", "msg-2", "msg-3"]


def test_cursor_by_message_id(client: TestClient) -> None:
    messages = _build_messages(3)
    mock_cp = MagicMock(spec=PostgresSaver)
    mock_cp.get_tuple.return_value = _checkpoint_tuple(messages=messages)
    set_history_checkpointer(mock_cp)

    response = client.get(
        "/internal/threads/thread-cursor/messages",
        params={"cursor": "msg-0", "limit": 5},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["items"][0]["message_id"] == "msg-1"
    assert body["items"][0]["content"] == "msg-1"


def test_client_actions_in_metadata(client: TestClient) -> None:
    action_payload: list[dict[str, Any]] = [
        {"tool": "jumpPage", "args": {"page": "pageA"}, "requires_approval": False}
    ]
    messages = [
        HumanMessage(content="go"),
        AIMessage(
            content="",
            id="ai-ca",
            additional_kwargs={CLIENT_ACTIONS_METADATA_KEY: action_payload},
        ),
    ]
    mock_cp = MagicMock(spec=PostgresSaver)
    mock_cp.get_tuple.return_value = _checkpoint_tuple(messages=messages)
    set_history_checkpointer(mock_cp)

    response = client.get("/internal/threads/thread-ca/messages")
    assert response.status_code == 200
    items = response.json()["items"]
    assert items[1]["role"] == "ai"
    assert items[1]["client_actions"] == [
        {
            "tool": "jumpPage",
            "args": {"page": "pageA"},
            "requires_approval": False,
        }
    ]


def test_limit_capped_at_100(client: TestClient) -> None:
    messages = _build_messages(150)
    mock_cp = MagicMock(spec=PostgresSaver)
    mock_cp.get_tuple.return_value = _checkpoint_tuple(messages=messages)
    set_history_checkpointer(mock_cp)

    response = client.get(
        "/internal/threads/thread-cap/messages",
        params={"limit": 500},
    )
    assert response.status_code == 200
    assert len(response.json()["items"]) == 100


def test_openapi_includes_history_route(client: TestClient) -> None:
    response = client.get("/openapi.json")
    assert response.status_code == 200
    paths = response.json()["paths"]
    assert "/internal/threads/{thread_id}/messages" in paths
    get_op = paths["/internal/threads/{thread_id}/messages"]["get"]
    assert get_op["tags"] == ["history"]


def test_blank_thread_id_returns_400(client: TestClient) -> None:
    response = client.get("/internal/threads/   /messages")
    assert response.status_code == 400
