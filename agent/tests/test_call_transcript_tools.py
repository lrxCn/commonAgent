"""Tests for Agent read-only call transcript tools."""

from __future__ import annotations

import json

import httpx
import pytest

from settings.config import Settings, reset_settings, set_settings_override
from tools.call_transcripts import (
    get_call_transcript,
    list_call_transcripts,
    reset_call_transcript_tool_user_id,
    set_call_transcript_tool_user_id,
)

_REQUIRED_ENV = {
    "LANGSMITH_API_KEY": "lsv2_test",
    "OPENAI_API_KEY": "sk-test",
    "DATABASE_URL": "postgresql://postgres:test@localhost:5432/common_agent",
}


@pytest.fixture(autouse=True)
def _settings() -> None:
    set_settings_override(
        Settings(
            **_REQUIRED_ENV,
            BACK_URL="http://back.test",
            INTERNAL_API_KEY="test-internal-key",
            BACK_INTERNAL_TIMEOUT_SECONDS=3,
        )
    )
    yield
    reset_settings()


def test_list_call_transcripts_uses_context_user_id(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    class FakeClient:
        def __init__(self, timeout: float) -> None:
            captured["timeout"] = timeout

        def __enter__(self) -> "FakeClient":
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def get(self, url: str, *, params: dict[str, object], headers: dict[str, str]) -> httpx.Response:
            captured["url"] = url
            captured["params"] = params
            captured["headers"] = headers
            return httpx.Response(
                200,
                json={"items": [{"call_id": "call-1"}]},
                request=httpx.Request("GET", url),
            )

    monkeypatch.setattr("tools.call_transcripts.httpx.Client", FakeClient)
    token = set_call_transcript_tool_user_id("u-alice")
    try:
        result = list_call_transcripts.invoke(
            {"peer_user_id": "u-bob", "since": "2026-06-01T00:00:00Z", "limit": 50}
        )
    finally:
        reset_call_transcript_tool_user_id(token)

    assert json.loads(result)["items"][0]["call_id"] == "call-1"
    assert captured["url"] == "http://back.test/internal/calls/transcripts"
    assert captured["params"] == {
        "user_id": "u-alice",
        "limit": 20,
        "peer_user_id": "u-bob",
        "since": "2026-06-01T00:00:00Z",
    }
    assert captured["headers"] == {"X-Internal-Key": "test-internal-key"}


def test_get_call_transcript_handles_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeClient:
        def __init__(self, timeout: float) -> None:
            del timeout

        def __enter__(self) -> "FakeClient":
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def get(self, *_args: object, **_kwargs: object) -> httpx.Response:
            return httpx.Response(
                404,
                json={"code": "NOT_FOUND"},
                request=httpx.Request("GET", "http://back.test/internal/calls/transcripts/missing"),
            )

    monkeypatch.setattr("tools.call_transcripts.httpx.Client", FakeClient)
    token = set_call_transcript_tool_user_id("u-alice")
    try:
        result = get_call_transcript.invoke({"call_id": "missing"})
    finally:
        reset_call_transcript_tool_user_id(token)

    assert json.loads(result) == {"error": "not_found", "message": "没有找到这条通话记录"}


def test_tools_require_runtime_user_id() -> None:
    with pytest.raises(RuntimeError, match="request context user_id"):
        list_call_transcripts.invoke({})
