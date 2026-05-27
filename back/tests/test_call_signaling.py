"""Integration tests for WebRTC call signaling (peers REST + WebSocket)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from api.app import create_app
from db.seed import run_seed
from db.session import clear_engine_cache, create_engine_from_url, get_session_factory
from services.call_signaling import call_signaling_hub
from settings.config import Settings, set_settings_override


@pytest.fixture
def call_client(tmp_path: Path) -> TestClient:
    db_file = tmp_path / "calls.db"
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

    call_signaling_hub.reset()
    client = TestClient(create_app())
    yield client
    call_signaling_hub.reset()
    set_settings_override(None)
    clear_engine_cache()


def _login(client: TestClient, username: str, password: str) -> None:
    response = client.post(
        "/api/auth/login",
        json={"username": username, "password": password},
    )
    assert response.status_code == 200


def _send_json(ws, payload: dict) -> None:
    ws.send_text(json.dumps(payload))


def test_peers_requires_login(call_client: TestClient) -> None:
    response = call_client.get("/api/calls/peers")
    assert response.status_code == 401


def test_peers_excludes_current_user(call_client: TestClient) -> None:
    _login(call_client, "alice", "demo123")
    response = call_client.get("/api/calls/peers")
    assert response.status_code == 200
    items = response.json()["items"]
    user_ids = {item["user_id"] for item in items}
    assert "u-alice" not in user_ids
    assert "u-bob" in user_ids
    assert "u-admin" in user_ids
    usernames = [item["username"] for item in items]
    assert usernames == sorted(usernames)


def test_ws_requires_login(call_client: TestClient) -> None:
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with call_client.websocket_connect("/api/calls/ws"):
            pass
    assert exc_info.value.code == 4401


def test_ws_connected_after_login(call_client: TestClient) -> None:
    _login(call_client, "alice", "demo123")
    with call_client.websocket_connect("/api/calls/ws") as ws:
        msg = ws.receive_json()
        assert msg == {"type": "connected", "user_id": "u-alice"}


def test_invite_incoming_reject(call_client: TestClient) -> None:
    alice = TestClient(call_client.app)
    bob = TestClient(call_client.app)
    _login(alice, "alice", "demo123")
    _login(bob, "bob", "demo123")

    with alice.websocket_connect("/api/calls/ws") as alice_ws:
        assert alice_ws.receive_json()["type"] == "connected"
        with bob.websocket_connect("/api/calls/ws") as bob_ws:
            assert bob_ws.receive_json()["type"] == "connected"

            _send_json(alice_ws, {"type": "call.invite", "to_user_id": "u-bob"})
            ringing = alice_ws.receive_json()
            assert ringing["type"] == "call.ringing"
            call_id = ringing["call_id"]

            incoming = bob_ws.receive_json()
            assert incoming == {
                "type": "call.incoming",
                "call_id": call_id,
                "from_user_id": "u-alice",
                "from_display_name": "Alice",
            }

            _send_json(bob_ws, {"type": "call.reject", "call_id": call_id})
            rejected = alice_ws.receive_json()
            assert rejected == {"type": "call.rejected", "call_id": call_id}


def test_invite_accept_rtc_forward(call_client: TestClient) -> None:
    alice = TestClient(call_client.app)
    bob = TestClient(call_client.app)
    _login(alice, "alice", "demo123")
    _login(bob, "bob", "demo123")

    with alice.websocket_connect("/api/calls/ws") as alice_ws:
        alice_ws.receive_json()
        with bob.websocket_connect("/api/calls/ws") as bob_ws:
            bob_ws.receive_json()

            _send_json(alice_ws, {"type": "call.invite", "to_user_id": "u-bob"})
            call_id = alice_ws.receive_json()["call_id"]
            bob_ws.receive_json()

            _send_json(bob_ws, {"type": "call.accept", "call_id": call_id})
            assert alice_ws.receive_json() == {"type": "call.accepted", "call_id": call_id}
            assert bob_ws.receive_json() == {"type": "call.accepted", "call_id": call_id}

            offer_sdp = "v=0 offer-sdp"
            _send_json(
                alice_ws,
                {"type": "rtc.offer", "call_id": call_id, "sdp": offer_sdp},
            )
            assert bob_ws.receive_json() == {
                "type": "rtc.offer",
                "call_id": call_id,
                "sdp": offer_sdp,
            }

            answer_sdp = "v=0 answer-sdp"
            _send_json(
                bob_ws,
                {"type": "rtc.answer", "call_id": call_id, "sdp": answer_sdp},
            )
            assert alice_ws.receive_json() == {
                "type": "rtc.answer",
                "call_id": call_id,
                "sdp": answer_sdp,
            }

            candidate = {
                "candidate": "candidate:1",
                "sdpMid": "0",
                "sdpMLineIndex": 0,
            }
            _send_json(
                alice_ws,
                {"type": "rtc.ice", "call_id": call_id, "candidate": candidate},
            )
            assert bob_ws.receive_json() == {
                "type": "rtc.ice",
                "call_id": call_id,
                "candidate": candidate,
            }


def test_invite_callee_offline(call_client: TestClient) -> None:
    alice = TestClient(call_client.app)
    _login(alice, "alice", "demo123")

    with alice.websocket_connect("/api/calls/ws") as alice_ws:
        alice_ws.receive_json()
        _send_json(alice_ws, {"type": "call.invite", "to_user_id": "u-bob"})
        failed = alice_ws.receive_json()
        assert failed["type"] == "call.failed"
        assert failed["code"] == "callee_offline"
        assert "call_id" in failed


def test_invite_busy_when_callee_in_call(call_client: TestClient) -> None:
    alice = TestClient(call_client.app)
    bob = TestClient(call_client.app)
    charlie = TestClient(call_client.app)
    _login(alice, "alice", "demo123")
    _login(bob, "bob", "demo123")
    _login(charlie, "admin", "123456")

    with alice.websocket_connect("/api/calls/ws") as alice_ws:
        alice_ws.receive_json()
        with bob.websocket_connect("/api/calls/ws") as bob_ws:
            bob_ws.receive_json()

            _send_json(alice_ws, {"type": "call.invite", "to_user_id": "u-bob"})
            call_id = alice_ws.receive_json()["call_id"]
            bob_ws.receive_json()
            _send_json(bob_ws, {"type": "call.accept", "call_id": call_id})
            alice_ws.receive_json()
            bob_ws.receive_json()

            with charlie.websocket_connect("/api/calls/ws") as charlie_ws:
                charlie_ws.receive_json()
                _send_json(charlie_ws, {"type": "call.invite", "to_user_id": "u-bob"})
                busy = charlie_ws.receive_json()
                assert busy == {"type": "call.busy", "call_id": busy["call_id"]}


def test_invalid_json_returns_error(call_client: TestClient) -> None:
    _login(call_client, "alice", "demo123")
    with call_client.websocket_connect("/api/calls/ws") as ws:
        ws.receive_json()
        ws.send_text("not-json")
        error = ws.receive_json()
        assert error["type"] == "error"
        assert error["code"] == "invalid_json"


def test_session_replaced_on_duplicate_connection(call_client: TestClient) -> None:
    _login(call_client, "alice", "demo123")
    with call_client.websocket_connect("/api/calls/ws") as first_ws:
        first_ws.receive_json()
        with call_client.websocket_connect("/api/calls/ws") as second_ws:
            second_ws.receive_json()
            replaced = first_ws.receive_json()
            assert replaced == {"type": "session.replaced"}
