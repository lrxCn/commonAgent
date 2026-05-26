"""Tests for Back admin KB routes: meta dual-write and Agent proxy."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest
import respx
from sqlalchemy import select
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient

from admin.kb import MAX_KB_CONTENT_BYTES
from api.app import create_app
from db.models import KbDocumentMeta, KbDocumentRole
from db.seed import run_seed
from db.session import clear_engine_cache, create_engine_from_url, get_session_factory
from settings.config import Settings, get_settings, set_settings_override


@pytest.fixture
def kb_client(tmp_path: Path) -> TestClient:
    db_file = tmp_path / "kb.db"
    database_url = f"sqlite+pysqlite:///{db_file}"
    back_root = Path(__file__).resolve().parents[1]

    set_settings_override(
        Settings(
            AGENT_URL="http://agent.test",
            INTERNAL_API_KEY="test-internal-key",
            DATABASE_URL=database_url,
            ADMIN_SEED_PASSWORD="123456",
            SESSION_SECRET="test-session-secret",
            CORS_ORIGINS="http://127.0.0.1:5173",
        )
    )

    alembic_cfg = Config(str(back_root / "alembic.ini"))
    alembic_cfg.set_main_option("script_location", str(back_root / "alembic"))
    alembic_cfg.set_main_option("sqlalchemy.url", database_url)
    alembic_cfg.set_main_option("prepend_sys_path", str(back_root / "src"))
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
def test_create_document_dual_writes_meta_and_junction(kb_client: TestClient) -> None:
    settings = get_settings()
    ingest_route = respx.post(f"{settings.AGENT_URL}/internal/kb/ingest").mock(
        return_value=httpx.Response(
            200,
            json={
                "doc_id": "doc-demo",
                "doc_name": "报销制度",
                "version": "1",
                "chunks_written": 3,
                "tokens_estimated": 120,
            },
        )
    )

    _login(kb_client, "admin", "123456")
    response = kb_client.post(
        "/api/admin/kb/documents",
        json={
            "role_ids": ["role-sales"],
            "doc_id": "doc-demo",
            "doc_name": "报销制度",
            "content": "报销需在30日内提交。",
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["doc_id"] == "doc-demo"
    assert body["role_ids"] == ["role-sales"]
    assert body["raw_content"] == "报销需在30日内提交。"
    assert body["chunks_written"] == 3
    assert body["tokens_estimated"] == 120
    assert ingest_route.called
    ingest_body = ingest_route.calls[0].request.content.decode()
    assert '"role_ids"' in ingest_body
    assert '"role-sales"' in ingest_body

    settings = get_settings()
    engine = create_engine_from_url(settings.DATABASE_URL)
    session_factory = get_session_factory(engine)
    with session_factory() as session:
        row = session.get(KbDocumentMeta, "doc-demo")
        assert row is not None
        assert row.raw_content == "报销需在30日内提交。"
        bindings = session.scalars(
            select(KbDocumentRole.role_id).where(KbDocumentRole.doc_id == "doc-demo")
        ).all()
        assert list(bindings) == ["role-sales"]
    engine.dispose()


@respx.mock
def test_create_document_with_multiple_roles(kb_client: TestClient) -> None:
    settings = get_settings()
    respx.post(f"{settings.AGENT_URL}/internal/kb/ingest").mock(
        return_value=httpx.Response(
            200,
            json={
                "doc_id": "doc-multi",
                "doc_name": "跨角色 FAQ",
                "version": "1",
                "chunks_written": 2,
                "tokens_estimated": 50,
            },
        )
    )

    _login(kb_client, "admin", "123456")
    response = kb_client.post(
        "/api/admin/kb/documents",
        json={
            "role_ids": ["role-sales", "role-support"],
            "doc_id": "doc-multi",
            "doc_name": "跨角色 FAQ",
            "content": "销售与支持共用。",
        },
    )
    assert response.status_code == 201
    assert response.json()["role_ids"] == ["role-sales", "role-support"]


@respx.mock
def test_get_document_reads_meta_and_agent_chunks(kb_client: TestClient) -> None:
    settings = get_settings()
    respx.post(f"{settings.AGENT_URL}/internal/kb/ingest").mock(
        return_value=httpx.Response(
            200,
            json={
                "doc_id": "doc-detail",
                "doc_name": "年假制度",
                "version": "1",
                "chunks_written": 2,
                "tokens_estimated": 80,
            },
        )
    )
    respx.get(f"{settings.AGENT_URL}/internal/kb/documents/doc-detail").mock(
        return_value=httpx.Response(
            200,
            json={
                "doc_id": "doc-detail",
                "doc_name": "年假制度",
                "version": "1",
                "role_ids": ["role-sales"],
                "chunks_written": 2,
                "chunks": [
                    {"chunk_id": "doc-detail:1:0000", "index": 0, "text": "chunk-one"},
                    {"chunk_id": "doc-detail:1:0001", "index": 1, "text": "chunk-two"},
                ],
            },
        )
    )

    _login(kb_client, "admin", "123456")
    kb_client.post(
        "/api/admin/kb/documents",
        json={
            "role_ids": ["role-sales"],
            "doc_id": "doc-detail",
            "doc_name": "年假制度",
            "content": "年假规则正文。",
        },
    )

    response = kb_client.get("/api/admin/kb/documents/doc-detail")
    assert response.status_code == 200
    body = response.json()
    assert body["raw_content"] == "年假规则正文。"
    assert body["role_ids"] == ["role-sales"]
    assert len(body["chunks"]) == 2
    assert body["chunks"][0]["text"] == "chunk-one"


@respx.mock
def test_list_documents_filters_by_role_contains(kb_client: TestClient) -> None:
    settings = get_settings()
    respx.post(f"{settings.AGENT_URL}/internal/kb/ingest").mock(
        return_value=httpx.Response(
            200,
            json={
                "doc_id": "doc-a",
                "doc_name": "A",
                "version": "1",
                "chunks_written": 1,
                "tokens_estimated": 10,
            },
        )
    )

    _login(kb_client, "admin", "123456")
    kb_client.post(
        "/api/admin/kb/documents",
        json={
            "role_ids": ["role-sales", "role-support"],
            "doc_id": "doc-a",
            "doc_name": "A",
            "content": "文档 A。",
        },
    )
    kb_client.post(
        "/api/admin/kb/documents",
        json={
            "role_ids": ["role-admin"],
            "doc_name": "B",
            "content": "文档 B。",
        },
    )

    sales_only = kb_client.get("/api/admin/kb/documents", params={"role_id": "role-sales"})
    assert sales_only.status_code == 200
    items = sales_only.json()["items"]
    assert len(items) == 1
    assert items[0]["doc_id"] == "doc-a"
    assert "role-sales" in items[0]["role_ids"]


@respx.mock
def test_delete_document_removes_meta_junction_and_calls_agent(kb_client: TestClient) -> None:
    settings = get_settings()
    respx.post(f"{settings.AGENT_URL}/internal/kb/ingest").mock(
        return_value=httpx.Response(
            200,
            json={
                "doc_id": "doc-del",
                "doc_name": "待删",
                "version": "1",
                "chunks_written": 1,
                "tokens_estimated": 10,
            },
        )
    )
    delete_route = respx.delete(
        f"{settings.AGENT_URL}/internal/kb/documents/doc-del",
    ).mock(return_value=httpx.Response(204))

    _login(kb_client, "admin", "123456")
    kb_client.post(
        "/api/admin/kb/documents",
        json={
            "role_ids": ["role-sales"],
            "doc_id": "doc-del",
            "doc_name": "待删",
            "content": "删除测试。",
        },
    )

    response = kb_client.delete("/api/admin/kb/documents/doc-del")
    assert response.status_code == 204
    assert delete_route.called

    engine = create_engine_from_url(settings.DATABASE_URL)
    session_factory = get_session_factory(engine)
    with session_factory() as session:
        assert session.get(KbDocumentMeta, "doc-del") is None
        bindings = session.scalars(
            select(KbDocumentRole).where(KbDocumentRole.doc_id == "doc-del")
        ).all()
        assert bindings == []
    engine.dispose()


@respx.mock
def test_patch_document_reingests_and_updates_meta_and_roles(kb_client: TestClient) -> None:
    settings = get_settings()
    respx.post(f"{settings.AGENT_URL}/internal/kb/ingest").mock(
        side_effect=[
            httpx.Response(
                200,
                json={
                    "doc_id": "doc-edit",
                    "doc_name": "政策",
                    "version": "1",
                    "chunks_written": 1,
                    "tokens_estimated": 20,
                },
            ),
            httpx.Response(
                200,
                json={
                    "doc_id": "doc-edit",
                    "doc_name": "政策",
                    "version": "2",
                    "chunks_written": 2,
                    "tokens_estimated": 40,
                },
            ),
        ]
    )

    _login(kb_client, "admin", "123456")
    kb_client.post(
        "/api/admin/kb/documents",
        json={
            "role_ids": ["role-sales"],
            "doc_id": "doc-edit",
            "doc_name": "政策",
            "content": "旧版内容。",
        },
    )

    response = kb_client.patch(
        "/api/admin/kb/documents/doc-edit",
        json={
            "role_ids": ["role-sales", "role-support"],
            "raw_content": "新版内容。",
            "version": "2",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["raw_content"] == "新版内容。"
    assert body["version"] == "2"
    assert body["chunks_written"] == 2
    assert body["role_ids"] == ["role-sales", "role-support"]


def test_kb_routes_require_admin(kb_client: TestClient) -> None:
    _login(kb_client, "alice", "demo123")
    response = kb_client.get("/api/admin/kb/documents")
    assert response.status_code == 403
    assert response.json()["code"] == "FORBIDDEN"


def test_create_document_rejects_oversized_content(kb_client: TestClient) -> None:
    _login(kb_client, "admin", "123456")
    oversized = "x" * (MAX_KB_CONTENT_BYTES + 1)
    response = kb_client.post(
        "/api/admin/kb/documents",
        json={
            "role_ids": ["role-sales"],
            "doc_name": "过大",
            "content": oversized,
        },
    )
    assert response.status_code == 409
    assert response.json()["code"] == "CONFLICT"


@respx.mock
def test_create_document_does_not_write_meta_when_ingest_fails(kb_client: TestClient) -> None:
    settings = get_settings()
    respx.post(f"{settings.AGENT_URL}/internal/kb/ingest").mock(
        return_value=httpx.Response(400, json={"detail": "embedding failed"})
    )

    _login(kb_client, "admin", "123456")
    response = kb_client.post(
        "/api/admin/kb/documents",
        json={
            "role_ids": ["role-sales"],
            "doc_id": "doc-fail",
            "doc_name": "失败文档",
            "content": "不会写入 meta。",
        },
    )
    assert response.status_code == 400

    engine = create_engine_from_url(settings.DATABASE_URL)
    session_factory = get_session_factory(engine)
    with session_factory() as session:
        assert session.get(KbDocumentMeta, "doc-fail") is None
    engine.dispose()
