"""Tests for call transcript persistence, summary, sensitive hits, and internal query."""

from __future__ import annotations

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from api.app import create_app
from db.seed import run_seed
from db.session import clear_engine_cache, create_engine_from_url, get_session_factory
from fastapi.testclient import TestClient
from settings.config import Settings, set_settings_override


@pytest.fixture
def transcripts_client(tmp_path: Path) -> TestClient:
    db_file = tmp_path / "transcripts.db"
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
            INTERNAL_API_KEY="test-internal-key",
            CALL_TRANSCRIPT_SENSITIVE_WORDS="投诉,退款,转账",
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


def _payload(*, peer_user_id: str = "u-bob") -> dict[str, object]:
    return {
        "peer_user_id": peer_user_id,
        "peer_display_name": "Bob",
        "started_at": "2026-06-01T10:00:00Z",
        "ended_at": "2026-06-01T10:03:00Z",
        "duration_ms": 180000,
        "lines": [
            {
                "track": "local",
                "role_label": "本地 · Alice",
                "text": "你好，我们聊一下报名信息。",
                "seq": 1,
            },
            {
                "track": "remote",
                "role_label": "对方 · Bob",
                "text": "可以，但是上次退款有投诉。",
                "seq": 2,
            },
        ],
    }


def test_post_transcript_requires_login(transcripts_client: TestClient) -> None:
    response = transcripts_client.post("/api/calls/call-1/transcript", json=_payload())
    assert response.status_code == 401


def test_post_transcript_upserts_summary_and_sensitive_hits(
    transcripts_client: TestClient,
) -> None:
    _login(transcripts_client, "alice", "demo123")
    first = transcripts_client.post("/api/calls/call-1/transcript", json=_payload())
    assert first.status_code == 200
    first_body = first.json()
    assert first_body["call_id"] == "call-1"

    second_payload = _payload()
    second_payload["duration_ms"] = 181000
    second = transcripts_client.post(
        "/api/calls/call-1/transcript", json=second_payload
    )
    assert second.status_code == 200
    assert second.json()["id"] == first_body["id"]

    listing = transcripts_client.get(
        "/internal/calls/transcripts",
        params={"user_id": "u-alice"},
        headers={"X-Internal-Key": "test-internal-key"},
    )
    assert listing.status_code == 200
    items = listing.json()["items"]
    assert len(items) == 1
    assert items[0]["summary"].startswith("你好，我们聊一下报名信息")
    assert items[0]["sensitive_hit_count"] == 2
    assert items[0]["sensitive_words"] == ["投诉", "退款"]

    detail = transcripts_client.get(
        "/internal/calls/transcripts/call-1",
        params={"user_id": "u-alice"},
        headers={"X-Internal-Key": "test-internal-key"},
    )
    assert detail.status_code == 200
    body = detail.json()
    assert body["duration_ms"] == 181000
    assert body["total_lines"] == 2
    assert body["lines"][1]["role_label"] == "对方 · Bob"
    assert {hit["word"] for hit in body["sensitive_hits"]} == {"投诉", "退款"}


def test_post_transcript_rejects_self_peer(transcripts_client: TestClient) -> None:
    _login(transcripts_client, "alice", "demo123")
    response = transcripts_client.post(
        "/api/calls/call-self/transcript",
        json=_payload(peer_user_id="u-alice"),
    )
    assert response.status_code == 400


def test_internal_requires_key_and_filters_user(transcripts_client: TestClient) -> None:
    _login(transcripts_client, "alice", "demo123")
    assert (
        transcripts_client.post(
            "/api/calls/call-1/transcript", json=_payload()
        ).status_code
        == 200
    )

    unauthorized = transcripts_client.get(
        "/internal/calls/transcripts",
        params={"user_id": "u-alice"},
    )
    assert unauthorized.status_code == 401

    bob_listing = transcripts_client.get(
        "/internal/calls/transcripts",
        params={"user_id": "u-bob"},
        headers={"X-Internal-Key": "test-internal-key"},
    )
    assert bob_listing.status_code == 200
    assert bob_listing.json()["items"] == []


def test_internal_filters_by_date_and_peer(transcripts_client: TestClient) -> None:
    _login(transcripts_client, "alice", "demo123")
    assert (
        transcripts_client.post(
            "/api/calls/call-1/transcript", json=_payload()
        ).status_code
        == 200
    )

    matched = transcripts_client.get(
        "/internal/calls/transcripts",
        params={
            "user_id": "u-alice",
            "peer_user_id": "u-bob",
            "since": "2026-06-01T00:00:00Z",
            "until": "2026-06-02T00:00:00Z",
        },
        headers={"X-Internal-Key": "test-internal-key"},
    )
    assert matched.status_code == 200
    assert len(matched.json()["items"]) == 1

    missed = transcripts_client.get(
        "/internal/calls/transcripts",
        params={
            "user_id": "u-alice",
            "since": "2026-06-02T00:00:00Z",
        },
        headers={"X-Internal-Key": "test-internal-key"},
    )
    assert missed.status_code == 200
    assert missed.json()["items"] == []
