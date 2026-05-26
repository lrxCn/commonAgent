"""Tests for Back chat context injection, tool union, and thread ownership."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
import respx
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import select

from api.app import create_app
from db.models import ChatThread, User, UserRole
from db.seed import run_seed
from db.session import clear_engine_cache, create_engine_from_url, get_session_factory
from services.context import (
    build_request_context,
    filter_tools_for_role_ids,
    load_role_tools,
)
from settings.config import Settings, get_settings, set_settings_override


def _sample_tools() -> list[dict]:
    return [
        {
            "name": "jumpPage",
            "description": "Navigate the user to an in-app page. Allowed pages: home (首页), students (学生管理), admin-roles (角色管理, admin only), admin-users (用户管理, admin only), admin-kb (RAG/知识库管理, admin only). Use the slug exactly as listed.",
            "parameters": {
                "type": "object",
                "properties": {
                    "page": {
                        "type": "string",
                        "enum": ["home", "students", "admin-roles", "admin-users", "admin-kb"],
                    }
                },
                "required": ["page"],
            },
            "requires_approval": False,
            "roles": ["role-admin", "role-sales"],
        },
        {
            "name": "createStudent",
            "description": "Open the create-student form on the Students page.",
            "parameters": {
                "type": "object",
                "properties": {
                    "student_no": {"type": "string"},
                    "name": {"type": "string"},
                    "class_name": {"type": "string"},
                    "status": {"type": "string", "enum": ["active", "inactive"]},
                },
                "required": [],
            },
            "requires_approval": True,
            "roles": ["role-admin", "role-sales"],
        },
    ]


def test_filter_tools_for_role_ids_union_dedup() -> None:
    tools = _sample_tools()
    allowed = filter_tools_for_role_ids(tools, ["role-sales", "role-admin"])
    names = [tool["name"] for tool in allowed]
    assert names == ["jumpPage", "createStudent"]
    assert "roles" not in allowed[0]


def test_filter_tools_for_role_ids_single_role() -> None:
    tools = _sample_tools()
    allowed = filter_tools_for_role_ids(tools, ["role-admin"])
    assert [tool["name"] for tool in allowed] == ["jumpPage", "createStudent"]


def test_filter_tools_for_role_ids_dedupes_by_name() -> None:
    tools = [
        *_sample_tools(),
        {
            "name": "jumpPage",
            "description": "Duplicate",
            "parameters": {"type": "object"},
            "roles": ["role-support"],
        },
    ]
    allowed = filter_tools_for_role_ids(tools, ["role-sales", "role-admin"])
    assert [tool["name"] for tool in allowed] == ["jumpPage", "createStudent"]


def test_build_request_context_includes_role_ids(tmp_path: Path) -> None:
    tools_file = tmp_path / "tools.json"
    tools_file.write_text(json.dumps({"tools": _sample_tools()}), encoding="utf-8")
    settings = Settings(
        DEMO_TOOLS_FILE=str(tools_file),
        DEMO_USER_ID="ignored",
        DEMO_ROLE_ID="ignored",
    )
    ctx = build_request_context(
        user_id="u-alice",
        role_ids=["role-sales"],
        settings=settings,
    )
    assert ctx["user_id"] == "u-alice"
    assert ctx["role_ids"] == ["role-sales"]
    assert ctx["role_id"] == "role-sales"
    assert [tool["name"] for tool in ctx["tools"]] == ["jumpPage", "createStudent"]


@pytest.fixture
def chat_client(tmp_path: Path) -> TestClient:
    db_file = tmp_path / "chat.db"
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
def test_api_chat_requires_login(chat_client: TestClient) -> None:
    respx.post("http://agent.test/internal/chat").mock(
        return_value=httpx.Response(200, json={"text": "ok"}),
    )
    response = chat_client.post(
        "/api/chat",
        json={"thread_id": "t-login", "message": "hello"},
    )
    assert response.status_code == 401


@respx.mock
def test_api_chat_registers_thread_and_forwards_role_ids(chat_client: TestClient) -> None:
    route = respx.post("http://agent.test/internal/chat").mock(
        return_value=httpx.Response(
            200,
            headers={"content-type": "text/event-stream"},
            content=b'data: {"type":"done"}\n\n',
        )
    )
    _login(chat_client, "alice", "demo123")

    response = chat_client.post(
        "/api/chat",
        json={"thread_id": "t-alice-1", "message": "hello"},
    )

    assert response.status_code == 200
    assert route.called
    body = json.loads(route.calls[0].request.content.decode())
    assert body["context"]["user_id"] == "u-alice"
    assert body["context"]["role_ids"] == ["role-sales"]
    assert body["context"]["role_id"] == "role-sales"
    assert [tool["name"] for tool in body["context"]["tools"]] == ["jumpPage", "createStudent"]

    engine = create_engine_from_url(get_settings().DATABASE_URL)
    session_factory = get_session_factory(engine)
    with session_factory() as session:
        thread = session.get(ChatThread, "t-alice-1")
        assert thread is not None
        assert thread.user_id == "u-alice"
    engine.dispose()


@respx.mock
def test_api_chat_thread_forbidden_for_other_user(chat_client: TestClient) -> None:
    respx.post("http://agent.test/internal/chat").mock(
        return_value=httpx.Response(200, json={"text": "ok"}),
    )
    _login(chat_client, "alice", "demo123")
    assert (
        chat_client.post(
            "/api/chat",
            json={"thread_id": "t-shared", "message": "hello"},
        ).status_code
        == 200
    )

    chat_client.post("/api/auth/logout")
    _login(chat_client, "bob", "demo123")
    response = chat_client.post(
        "/api/chat",
        json={"thread_id": "t-shared", "message": "intrude"},
    )

    assert response.status_code == 403
    body = response.json()
    assert body["code"] == "FORBIDDEN"
    assert body["message"] == "无权访问该会话"


@respx.mock
def test_api_chat_multi_role_tool_union(chat_client: TestClient) -> None:
    route = respx.post("http://agent.test/internal/chat").mock(
        return_value=httpx.Response(200, json={"text": "ok"}),
    )

    engine = create_engine_from_url(get_settings().DATABASE_URL)
    session_factory = get_session_factory(engine)
    with session_factory() as session:
        user = session.scalar(select(User).where(User.username == "alice"))
        assert user is not None
        session.add(UserRole(user_id=user.user_id, role_id="role-support"))
        session.commit()
    engine.dispose()

    _login(chat_client, "alice", "demo123")
    response = chat_client.post(
        "/api/chat",
        json={"thread_id": "t-alice-multi", "message": "help"},
    )

    assert response.status_code == 200
    body = json.loads(route.calls[0].request.content.decode())
    assert body["context"]["role_ids"] == ["role-sales", "role-support"]
    tool_names = [tool["name"] for tool in body["context"]["tools"]]
    assert tool_names == ["jumpPage", "createStudent"]


def test_demo_tools_file_has_roles_arrays() -> None:
    back_root = Path(__file__).resolve().parents[1]
    tools = load_role_tools(back_root / "config" / "tools.demo.json")
    assert [tool["name"] for tool in tools] == ["jumpPage", "createStudent"]
    for tool in tools:
        assert isinstance(tool.get("roles"), list)
        assert tool["roles"]
    page_enum = tools[0]["parameters"]["properties"]["page"]["enum"]
    assert page_enum == ["home", "students", "admin-roles", "admin-users", "admin-kb"]
    create_params = tools[1]["parameters"]["properties"]
    assert create_params["status"]["enum"] == ["active", "inactive"]
    assert tools[1]["parameters"]["required"] == []
