"""Tests for Back admin CRUD: roles/users, 403, 409, admin protection."""

from __future__ import annotations

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient

from admin.users import ADMIN_SEED_USER_ID
from api.app import create_app
from db.models import KbDocumentMeta
from db.seed import run_seed
from db.session import clear_engine_cache, create_engine_from_url, get_session_factory
from settings.config import Settings, get_settings, set_settings_override


@pytest.fixture
def admin_client(tmp_path: Path) -> TestClient:
    db_file = tmp_path / "admin.db"
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


def _login(client: TestClient, username: str, password: str) -> None:
    response = client.post(
        "/api/auth/login",
        json={"username": username, "password": password},
    )
    assert response.status_code == 200


def test_admin_routes_require_login(admin_client: TestClient) -> None:
    response = admin_client.get("/api/admin/roles")
    assert response.status_code == 401
    assert response.json()["code"] == "UNAUTHORIZED"


def test_admin_routes_forbid_non_admin(admin_client: TestClient) -> None:
    _login(admin_client, "alice", "demo123")
    response = admin_client.get("/api/admin/roles")
    assert response.status_code == 403
    assert response.json()["code"] == "FORBIDDEN"


def test_list_roles_includes_counts(admin_client: TestClient) -> None:
    _login(admin_client, "admin", "123456")
    response = admin_client.get("/api/admin/roles")
    assert response.status_code == 200
    roles = response.json()
    assert len(roles) == 3
    by_id = {item["role_id"]: item for item in roles}
    assert by_id["role-admin"]["user_count"] == 1
    assert by_id["role-sales"]["user_count"] == 1
    assert by_id["role-support"]["user_count"] == 1
    assert all(item["document_count"] == 0 for item in roles)


def test_create_and_update_role(admin_client: TestClient) -> None:
    _login(admin_client, "admin", "123456")
    create = admin_client.post(
        "/api/admin/roles",
        json={
            "role_id": "role-marketing",
            "name": "市场",
            "description": "市场资料",
        },
    )
    assert create.status_code == 201
    created = create.json()
    assert created["role_id"] == "role-marketing"
    assert created["user_count"] == 0

    patch = admin_client.patch(
        "/api/admin/roles/role-marketing",
        json={"name": "市场部", "description": "更新描述"},
    )
    assert patch.status_code == 200
    assert patch.json()["name"] == "市场部"
    assert patch.json()["description"] == "更新描述"


def test_invalid_role_id_returns_conflict(admin_client: TestClient) -> None:
    _login(admin_client, "admin", "123456")
    response = admin_client.post(
        "/api/admin/roles",
        json={"role_id": "invalid", "name": "无效"},
    )
    assert response.status_code == 409
    assert response.json()["field_errors"]["role_id"] == "格式无效"


def test_delete_role_with_users_returns_409(admin_client: TestClient) -> None:
    _login(admin_client, "admin", "123456")
    response = admin_client.delete("/api/admin/roles/role-sales")
    assert response.status_code == 409
    assert response.json()["code"] == "CONFLICT"
    assert "用户" in response.json()["message"]


def test_delete_role_with_documents_returns_409(admin_client: TestClient) -> None:
    _login(admin_client, "admin", "123456")
    admin_client.post(
        "/api/admin/roles",
        json={"role_id": "role-marketing", "name": "市场"},
    )

    settings = get_settings()
    engine = create_engine_from_url(settings.DATABASE_URL)
    session_factory = get_session_factory(engine)
    with session_factory() as session:
        session.add(
            KbDocumentMeta(
                doc_id="doc-001",
                role_id="role-marketing",
                doc_name="价目表",
                version="1",
                raw_content="demo",
            )
        )
        session.commit()
    engine.dispose()

    response = admin_client.delete("/api/admin/roles/role-marketing")
    assert response.status_code == 409
    assert "文档" in response.json()["message"]


def test_create_user_with_multiple_roles_and_me_reflects(
    admin_client: TestClient,
) -> None:
    _login(admin_client, "admin", "123456")
    create = admin_client.post(
        "/api/admin/users",
        json={
            "username": "carol",
            "password": "demo123",
            "display_name": "Carol",
            "role_ids": ["role-sales", "role-support"],
        },
    )
    assert create.status_code == 201
    created = create.json()
    assert set(created["role_ids"]) == {"role-sales", "role-support"}

    admin_client.post("/api/auth/logout")
    _login(admin_client, "carol", "demo123")
    me = admin_client.get("/api/me")
    assert me.status_code == 200
    assert set(me.json()["role_ids"]) == {"role-sales", "role-support"}


def test_update_user_roles_reflected_in_me(admin_client: TestClient) -> None:
    _login(admin_client, "admin", "123456")
    users = admin_client.get("/api/admin/users").json()
    alice = next(item for item in users if item["username"] == "alice")

    patch = admin_client.patch(
        f"/api/admin/users/{alice['user_id']}",
        json={"role_ids": ["role-sales", "role-support"]},
    )
    assert patch.status_code == 200
    assert set(patch.json()["role_ids"]) == {"role-sales", "role-support"}

    admin_client.post("/api/auth/logout")
    _login(admin_client, "alice", "demo123")
    me = admin_client.get("/api/me")
    assert set(me.json()["role_ids"]) == {"role-sales", "role-support"}


def test_create_user_without_roles_returns_409(admin_client: TestClient) -> None:
    _login(admin_client, "admin", "123456")
    response = admin_client.post(
        "/api/admin/users",
        json={
            "username": "empty",
            "password": "demo123",
            "display_name": "Empty",
            "role_ids": [],
        },
    )
    assert response.status_code == 422


def test_cannot_delete_admin_user(admin_client: TestClient) -> None:
    _login(admin_client, "admin", "123456")
    response = admin_client.delete(f"/api/admin/users/{ADMIN_SEED_USER_ID}")
    assert response.status_code == 403
    assert response.json()["code"] == "FORBIDDEN"


def test_cannot_remove_admin_flag_from_admin(admin_client: TestClient) -> None:
    _login(admin_client, "admin", "123456")
    response = admin_client.patch(
        f"/api/admin/users/{ADMIN_SEED_USER_ID}",
        json={"is_admin": False},
    )
    assert response.status_code == 403


def test_cannot_remove_role_admin_from_admin(admin_client: TestClient) -> None:
    _login(admin_client, "admin", "123456")
    response = admin_client.patch(
        f"/api/admin/users/{ADMIN_SEED_USER_ID}",
        json={"role_ids": ["role-sales"]},
    )
    assert response.status_code == 409
    assert "role-admin" in response.json()["message"]


def test_delete_custom_user(admin_client: TestClient) -> None:
    _login(admin_client, "admin", "123456")
    create = admin_client.post(
        "/api/admin/users",
        json={
            "username": "temp-user",
            "password": "demo123",
            "display_name": "Temp",
            "role_ids": ["role-sales"],
        },
    )
    user_id = create.json()["user_id"]

    delete = admin_client.delete(f"/api/admin/users/{user_id}")
    assert delete.status_code == 204

    gone = admin_client.get(f"/api/admin/users/{user_id}")
    assert gone.status_code == 404
