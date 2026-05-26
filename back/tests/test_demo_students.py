"""Tests for Back student CRUD: list, create, update, delete, 409, 401."""

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
def students_client(tmp_path: Path) -> TestClient:
    db_file = tmp_path / "students.db"
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


def test_list_students_requires_login(students_client: TestClient) -> None:
    response = students_client.get("/api/students")
    assert response.status_code == 401
    assert response.json()["code"] == "UNAUTHORIZED"


def test_list_students_returns_seed_data(students_client: TestClient) -> None:
    _login(students_client, "alice", "demo123")
    response = students_client.get("/api/students")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 3
    assert len(body["items"]) == 3
    assert body["offset"] == 0
    assert body["limit"] == 20
    student_nos = {item["student_no"] for item in body["items"]}
    assert student_nos == {"2024001", "2024002", "2024003"}


def test_search_students_by_name(students_client: TestClient) -> None:
    _login(students_client, "admin", "123456")
    response = students_client.get("/api/students", params={"search": "张三"})
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["name"] == "张三"


def test_alice_creates_student_admin_can_see_and_edit(students_client: TestClient) -> None:
    _login(students_client, "alice", "demo123")
    create = students_client.post(
        "/api/students",
        json={
            "student_no": "2024999",
            "name": "赵六",
            "class_name": "高一(3)班",
            "status": "active",
        },
    )
    assert create.status_code == 201
    created = create.json()
    assert created["student_no"] == "2024999"
    assert created["name"] == "赵六"
    student_id = created["student_id"]

    students_client.post("/api/auth/logout")

    _login(students_client, "admin", "123456")
    listing = students_client.get("/api/students", params={"search": "2024999"})
    assert listing.status_code == 200
    assert listing.json()["total"] == 1

    patch = students_client.patch(
        f"/api/students/{student_id}",
        json={"name": "赵六（已改）"},
    )
    assert patch.status_code == 200
    assert patch.json()["name"] == "赵六（已改）"

    delete = students_client.delete(f"/api/students/{student_id}")
    assert delete.status_code == 204

    gone = students_client.get(f"/api/students/{student_id}")
    assert gone.status_code == 404


def test_duplicate_student_no_returns_409(students_client: TestClient) -> None:
    _login(students_client, "bob", "demo123")
    response = students_client.post(
        "/api/students",
        json={
            "student_no": "2024001",
            "name": "冲突学生",
            "class_name": "高一(1)班",
        },
    )
    assert response.status_code == 409
    body = response.json()
    assert body["code"] == "CONFLICT"
    assert body["message"] == "学号已存在"
    assert body["field_errors"] == {"student_no": "已占用"}


def test_update_to_duplicate_student_no_returns_409(students_client: TestClient) -> None:
    _login(students_client, "alice", "demo123")
    listing = students_client.get("/api/students", params={"search": "2024003"})
    student_id = listing.json()["items"][0]["student_id"]

    response = students_client.patch(
        f"/api/students/{student_id}",
        json={"student_no": "2024001"},
    )
    assert response.status_code == 409
    assert response.json()["field_errors"]["student_no"] == "已占用"


def test_batch_delete_students(students_client: TestClient) -> None:
    _login(students_client, "admin", "123456")
    listing = students_client.get("/api/students")
    ids = [item["student_id"] for item in listing.json()["items"][:2]]

    response = students_client.post(
        "/api/students/batch-delete",
        json={"student_ids": ids},
    )
    assert response.status_code == 200
    assert response.json()["deleted"] == 2

    remaining = students_client.get("/api/students")
    assert remaining.json()["total"] == 1
