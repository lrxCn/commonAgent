"""Integration tests for Back ASR WebSocket proxy (/api/asr/ws)."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from api.app import create_app
from db.seed import run_seed
from db.session import clear_engine_cache, create_engine_from_url, get_session_factory
from services.asr_proxy import asr_session_manager
from services.volc_asr.protocol import VolcAsrResponse
from services.xunfei_asr import extract_xunfei_text
from settings.config import Settings, set_settings_override


class FakeVolcAsrClient:
    created: list["FakeVolcAsrClient"] = []
    full_request_code: int | None = None

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.user_id: str | None = None
        self.audio_chunks: list[tuple[bytes, bool]] = []
        self._responses: asyncio.Queue[VolcAsrResponse] = asyncio.Queue()
        FakeVolcAsrClient.created.append(self)

    @classmethod
    def reset(cls) -> None:
        cls.created.clear()
        cls.full_request_code = None

    async def connect(self) -> None:
        return None

    async def send_full_request(self, user_id: str) -> VolcAsrResponse | None:
        self.user_id = user_id
        if FakeVolcAsrClient.full_request_code is not None:
            return VolcAsrResponse(code=FakeVolcAsrClient.full_request_code)
        return None

    async def send_audio(self, pcm: bytes, *, is_last: bool = False) -> None:
        self.audio_chunks.append((pcm, is_last))
        if is_last:
            await self._responses.put(
                VolcAsrResponse(
                    payload_msg={
                        "result": {
                            "text": "你好",
                            "utterances": [
                                {
                                    "text": "你好",
                                    "definite": True,
                                    "start_time": 0,
                                    "end_time": 500,
                                }
                            ],
                        }
                    },
                    is_last_package=True,
                )
            )

    async def recv_response(self) -> VolcAsrResponse | None:
        return await self._responses.get()

    async def close(self) -> None:
        return None


def _fake_client_factory(_settings: Settings) -> FakeVolcAsrClient:
    return FakeVolcAsrClient(_settings)


def _make_settings(database_url: str, *, access_key: str | None = "test-access-key") -> Settings:
    return Settings(
        DATABASE_URL=database_url,
        ADMIN_SEED_PASSWORD="123456",
        SESSION_SECRET="test-session-secret",
        CORS_ORIGINS="http://127.0.0.1:5173,http://localhost:5173",
        VOLC_ASR_ACCESS_KEY=access_key,
        XUNFEI_ASR_APP_ID=None,
        XUNFEI_ASR_API_KEY=None,
        XUNFEI_ASR_API_SECRET=None,
        STT_API_KEY=None,
        SILICONFLOW_STT_API_KEY=None,
        SILICONFLOW_API_KEY=None,
    )


@pytest.fixture
def asr_client(tmp_path: Path) -> TestClient:
    db_file = tmp_path / "asr.db"
    database_url = f"sqlite+pysqlite:///{db_file}"
    back_root = Path(__file__).resolve().parents[1]

    alembic_cfg = Config(str(back_root / "alembic.ini"))
    alembic_cfg.set_main_option("script_location", str(back_root / "alembic"))
    alembic_cfg.set_main_option("sqlalchemy.url", database_url)
    alembic_cfg.set_main_option("prepend_sys_path", str(back_root / "src"))

    set_settings_override(_make_settings(database_url))
    command.upgrade(alembic_cfg, "head")

    engine = create_engine_from_url(database_url)
    session_factory = get_session_factory(engine)
    run_seed(session_factory, admin_password="123456")
    engine.dispose()

    FakeVolcAsrClient.reset()
    asr_session_manager.reset()
    asr_session_manager.client_factory = _fake_client_factory

    client = TestClient(create_app())
    yield client

    asr_session_manager.reset()
    asr_session_manager.client_factory = _fake_client_factory
    FakeVolcAsrClient.reset()
    set_settings_override(None)
    clear_engine_cache()


def _login(client: TestClient, username: str, password: str) -> None:
    response = client.post(
        "/api/auth/login",
        json={"username": username, "password": password},
    )
    assert response.status_code == 200


def _send_json(ws, payload: dict[str, Any]) -> None:
    ws.send_text(json.dumps(payload))


def test_asr_ws_requires_login(asr_client: TestClient) -> None:
    with pytest.raises(WebSocketDisconnect):
        with asr_client.websocket_connect("/api/asr/ws"):
            pass


def test_asr_ws_start_audio_stop_flow(asr_client: TestClient) -> None:
    _login(asr_client, "alice", "demo123")

    pcm = b"\x00\x01" * 3200

    with asr_client.websocket_connect("/api/asr/ws") as ws:
        assert ws.receive_json() == {"type": "connected", "user_id": "u-alice"}

        _send_json(
            ws,
            {
                "type": "asr.start",
                "scene": "call",
                "track": "local",
                "call_id": "call-1",
            },
        )

        ws.send_bytes(pcm)
        ws.send_bytes(pcm)

        _send_json(ws, {"type": "asr.stop", "track": "local"})

        messages = [ws.receive_json() for _ in range(2)]

        types = {msg["type"] for msg in messages}
        assert "asr.final" in types
        assert "asr.ended" in types

        final_msg = next(m for m in messages if m["type"] == "asr.final")
        assert final_msg["track"] == "local"
        assert final_msg["text"] == "你好"

    assert len(FakeVolcAsrClient.created) == 1
    upstream = FakeVolcAsrClient.created[0]
    assert upstream.user_id == "u-alice"
    assert upstream.audio_chunks
    assert upstream.audio_chunks[-1][1] is True


def test_asr_ws_full_request_upstream_error(asr_client: TestClient) -> None:
    _login(asr_client, "alice", "demo123")
    FakeVolcAsrClient.full_request_code = 40000001

    with asr_client.websocket_connect("/api/asr/ws") as ws:
        ws.receive_json()
        _send_json(
            ws,
            {"type": "asr.start", "scene": "call", "track": "local", "call_id": "call-1"},
        )
        err = ws.receive_json()
        assert err == {
            "type": "asr.error",
            "code": "upstream_error",
            "message": "上游错误 code=40000001",
        }

    assert len(FakeVolcAsrClient.created) == 1
    assert FakeVolcAsrClient.created[0].audio_chunks == []


def test_asr_ws_stop_without_pcm_skips_upstream(asr_client: TestClient) -> None:
    _login(asr_client, "alice", "demo123")

    with asr_client.websocket_connect("/api/asr/ws") as ws:
        ws.receive_json()
        _send_json(
            ws,
            {"type": "asr.start", "scene": "call", "track": "local", "call_id": "call-1"},
        )
        _send_json(ws, {"type": "asr.stop", "track": "local"})

    assert len(FakeVolcAsrClient.created) == 1
    assert FakeVolcAsrClient.created[0].audio_chunks == []


def test_suppresses_packet_timeout_without_browser_pcm() -> None:
    from unittest.mock import MagicMock

    from services.asr_proxy import (
        UPSTREAM_CODE_PACKET_TIMEOUT,
        AsrTrackSession,
    )

    session = AsrTrackSession(
        user_id="u-alice",
        track="local",
        websocket=MagicMock(),
        settings=_make_settings("sqlite:///:memory:"),
    )
    assert session._should_suppress_upstream_error(UPSTREAM_CODE_PACKET_TIMEOUT) is True
    session.has_received_pcm = True
    assert session._should_suppress_upstream_error(UPSTREAM_CODE_PACKET_TIMEOUT) is False
    assert session._should_suppress_upstream_error(45000151) is False


def test_asr_ws_credentials_missing(tmp_path: Path) -> None:
    db_file = tmp_path / "asr-no-creds.db"
    database_url = f"sqlite+pysqlite:///{db_file}"
    back_root = Path(__file__).resolve().parents[1]

    alembic_cfg = Config(str(back_root / "alembic.ini"))
    alembic_cfg.set_main_option("script_location", str(back_root / "alembic"))
    alembic_cfg.set_main_option("sqlalchemy.url", database_url)
    alembic_cfg.set_main_option("prepend_sys_path", str(back_root / "src"))

    set_settings_override(_make_settings(database_url, access_key=None))
    command.upgrade(alembic_cfg, "head")

    engine = create_engine_from_url(database_url)
    session_factory = get_session_factory(engine)
    run_seed(session_factory, admin_password="123456")
    engine.dispose()

    asr_session_manager.reset()
    asr_session_manager.client_factory = _fake_client_factory
    client = TestClient(create_app())

    try:
        _login(client, "alice", "demo123")
        with client.websocket_connect("/api/asr/ws") as ws:
            ws.receive_json()
            _send_json(
                ws,
                {"type": "asr.start", "scene": "call", "track": "local"},
            )
            err = ws.receive_json()
            assert err == {
                "type": "asr.error",
                "code": "credentials_missing",
                "message": "ASR 凭证未配置",
            }
        assert FakeVolcAsrClient.created == []
    finally:
        asr_session_manager.reset()
        set_settings_override(None)
        clear_engine_cache()


def test_xunfei_result_extracts_text_and_final() -> None:
    text, is_final = extract_xunfei_text(
        {
            "code": 0,
            "data": {
                "status": 2,
                "result": {
                    "ws": [
                        {"cw": [{"w": "你好"}]},
                        {"cw": [{"w": "世界"}]},
                    ]
                },
            },
        }
    )
    assert text == "你好世界"
    assert is_final is True
