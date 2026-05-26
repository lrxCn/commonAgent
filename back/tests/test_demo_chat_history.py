"""Tests for Back thread history proxy and ownership checks."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
import respx
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient

from api.app import create_app
from db.seed import run_seed
from db.session import clear_engine_cache, create_engine_from_url, get_session_factory
from settings.config import Settings, set_settings_override


def _sample_tools() -> list[dict]:
    return [
        {
            "name": "jumpPage",
            "description": "Go to page",
            "parameters": {"type": "object", "properties": {"page": {"type": "string"}}},
            "requires_approval": False,
            "roles": ["role-admin", "role-sales"],
        },
    ]


@pytest.fixture
def history_client(tmp_path: Path) -> TestClient:
    db_file = tmp_path / "history.db"
    database_url = f"sqlite+pysqlite:///{db_file}"
    back_root = Path(__file__).resolve().parents[1]
    tools_file = tmp_path / "tools.json"
    tools_file.write_text(json.dumps({"tools": _sample_tools()}), encoding="utf-8")

    alembic_cfg = Config(str(back_root / "alembic.ini"))
    alembic_cfg.set_main_option("script_location", str(back_root / "alembic"))
    alembic_cfg.set_main_option("sqlalchemy.url", database_url)
    alembic_cfg.set_main_option("prepend_sys_path", str(back_root / "src"))

    set_settings_override(
        Settings(
            DATABASE_URL=database_url,
            ADMIN_SEED_PASSWORD="123456",
            SESSION_SECRET="test-session-secret",
            AGENT_URL="http://agent.test",
            INTERNAL_API_KEY="test-internal-key",
            DEMO_TOOLS_FILE=str(tools_file),
        )
    )
    command.upgrade(alembic_cfg, "head")

    engine = create_engine_from_url(database_url)
    session_factory = get_session_factory(engine)
    run_seed(session_factory, admin_password="123456")
    engine.dispose()

    client = TestClient(create_app())
    yield client
    set_settings_override(None)
    clear_engine_cache()


def _login(client: TestClient, username: str, password: str) -> None:
    response = client.post(
        "/api/auth/login",
        json={"username": username, "password": password},
    )
    assert response.status_code == 200


@respx.mock
def test_thread_messages_requires_login(history_client: TestClient) -> None:
    respx.get("http://agent.test/internal/threads/t-1/messages").mock(
        return_value=httpx.Response(200, json={"items": [], "next_cursor": None}),
    )
    response = history_client.get("/api/threads/t-1/messages")
    assert response.status_code == 401


@respx.mock
def test_thread_messages_proxies_to_agent(history_client: TestClient) -> None:
    route = respx.get("http://agent.test/internal/threads/t-alice-hist/messages").mock(
        return_value=httpx.Response(
            200,
            json={
                "items": [
                    {
                        "message_id": "m1",
                        "role": "human",
                        "content": "你好",
                        "timestamp": None,
                        "client_actions": None,
                    },
                    {
                        "message_id": "m2",
                        "role": "ai",
                        "content": "你好！",
                        "timestamp": None,
                        "client_actions": None,
                    },
                ],
                "next_cursor": None,
            },
        ),
    )
    _login(history_client, "alice", "demo123")

    response = history_client.get("/api/threads/t-alice-hist/messages")

    assert response.status_code == 200
    assert route.called
    assert route.calls[0].request.headers["X-Internal-Key"] == "test-internal-key"
    body = response.json()
    assert len(body["items"]) == 2
    assert body["items"][0]["role"] == "human"


@respx.mock
def test_thread_messages_forbidden_for_other_user(history_client: TestClient) -> None:
    respx.post("http://agent.test/internal/chat").mock(
        return_value=httpx.Response(200, json={"text": "ok"}),
    )
    respx.get("http://agent.test/internal/threads/t-shared/messages").mock(
        return_value=httpx.Response(200, json={"items": [], "next_cursor": None}),
    )

    _login(history_client, "alice", "demo123")
    assert (
        history_client.post(
            "/api/chat",
            json={"thread_id": "t-shared", "message": "hello"},
        ).status_code
        == 200
    )

    history_client.post("/api/auth/logout")
    _login(history_client, "bob", "demo123")
    response = history_client.get("/api/threads/t-shared/messages")

    assert response.status_code == 403
    body = response.json()
    assert body["code"] == "FORBIDDEN"
    assert body["message"] == "无权访问该会话"


@respx.mock
def test_thread_messages_allows_unregistered_thread(history_client: TestClient) -> None:
    route = respx.get("http://agent.test/internal/threads/t-new/messages").mock(
        return_value=httpx.Response(200, json={"items": [], "next_cursor": None}),
    )
    _login(history_client, "alice", "demo123")

    response = history_client.get("/api/threads/t-new/messages")

    assert response.status_code == 200
    assert route.called
    assert response.json()["items"] == []
