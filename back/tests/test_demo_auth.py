"""Tests for Back Cookie Session auth: login, logout, /api/me, CORS."""

from __future__ import annotations

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient

from api.app import create_app
from db.seed import run_seed
from db.session import clear_engine_cache, create_engine_from_url, get_session_factory
from settings.config import Settings, set_settings_override


@pytest.fixture
def auth_client(tmp_path: Path) -> TestClient:
    db_file = tmp_path / "auth.db"
    database_url = f"sqlite+pysqlite:///{db_file}"
    back_root = Path(__file__).resolve().parents[1]

    alembic_cfg = Config(str(back_root / "alembic.ini"))
    alembic_cfg.set_main_option("script_location", str(back_root / "alembic"))
    alembic_cfg.set_main_option("sqlalchemy.url", database_url)
    alembic_cfg.set_main_option("prepend_sys_path", str(back_root / "src"))

    set_settings_override(
        Settings(
            DATABASE_URL=database_url,
            ADMIN_SEED_PASSWORD="123456",
            SESSION_SECRET="test-session-secret",
            CORS_ORIGINS="http://127.0.0.1:5173,http://localhost:5173",
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


def _login(client: TestClient, username: str, password: str) -> dict:
    response = client.post(
        "/api/auth/login",
        json={"username": username, "password": password},
    )
    assert response.status_code == 200
    return response.json()


def test_login_admin_returns_role_ids(auth_client: TestClient) -> None:
    data = _login(auth_client, "admin", "123456")
    assert data["user_id"] == "u-admin"
    assert data["username"] == "admin"
    assert data["is_admin"] is True
    assert data["role_ids"] == ["role-admin"]
    assert data["roles"] == [{"role_id": "role-admin", "name": "管理员"}]


def test_login_alice_returns_role_ids(auth_client: TestClient) -> None:
    data = _login(auth_client, "alice", "demo123")
    assert data["user_id"] == "u-alice"
    assert data["role_ids"] == ["role-sales"]
    assert data["roles"][0]["name"] == "销售"


def test_login_bob_returns_role_ids(auth_client: TestClient) -> None:
    data = _login(auth_client, "bob", "demo123")
    assert data["user_id"] == "u-bob"
    assert data["role_ids"] == ["role-support"]
    assert data["roles"][0]["name"] == "客服"


def test_login_wrong_password_returns_unified_message(auth_client: TestClient) -> None:
    response = auth_client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "wrong"},
    )
    assert response.status_code == 401
    body = response.json()
    assert body["code"] == "UNAUTHORIZED"
    assert body["message"] == "用户名或密码错误"
    assert body["field_errors"] == {}


def test_me_requires_login(auth_client: TestClient) -> None:
    response = auth_client.get("/api/me")
    assert response.status_code == 401
    body = response.json()
    assert body["code"] == "UNAUTHORIZED"


def test_me_after_login(auth_client: TestClient) -> None:
    _login(auth_client, "alice", "demo123")
    response = auth_client.get("/api/me")
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "alice"
    assert data["display_name"] == "Alice"
    assert data["role_ids"] == ["role-sales"]


def test_logout_clears_session(auth_client: TestClient) -> None:
    _login(auth_client, "admin", "123456")
    logout = auth_client.post("/api/auth/logout")
    assert logout.status_code == 204

    response = auth_client.get("/api/me")
    assert response.status_code == 401


def test_cors_allows_credentials_for_vite_origin(auth_client: TestClient) -> None:
    response = auth_client.options(
        "/api/me",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"
    assert response.headers.get("access-control-allow-credentials") == "true"
