"""Inbound guardrails — unit tests and gateway integration."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from gateway.app import create_app
from guardrails.inbound import (
    HIGH_RISK_TEST_SAMPLE,
    INJECTION_TEST_SAMPLE,
    POLITICAL_SENSITIVE_TEST_SAMPLE,
    UNSUPPORTED_POLITICAL_MESSAGE,
    UNSUPPORTED_RISK_MESSAGE,
    check_inbound,
    register_inbound_hook,
)
from guardrails.types import GuardResult
from settings.config import Settings, reset_settings, set_settings_override
from tests.support.gateway_graph import install_gateway_graph_mocks, teardown_gateway_graph_mocks

_REQUIRED = {
    "LANGSMITH_API_KEY": "lsv2_test",
    "OPENAI_API_KEY": "sk-test",
    "DATABASE_URL": "postgresql://postgres:test@localhost:5432/common_agent",
}

_VALID_CHAT_PAYLOAD = {
    "thread_id": "550e8400-e29b-41d4-a716-446655440000",
    "message": "你好，请帮我查一下订单状态。",
    "context": {
        "user_id": "user-1",
        "role_id": "role-sales",
        "tools": [],
    },
}

_TEST_SETTINGS = Settings(
    LANGSMITH_API_KEY="lsv2_test",
    OPENAI_API_KEY="sk-test",
    DATABASE_URL=_REQUIRED["DATABASE_URL"],
    GUARDRAILS_ENABLED=True,
)


@pytest.fixture(autouse=True)
def _reset_hook() -> None:
    register_inbound_hook(None)
    yield
    register_inbound_hook(None)


@pytest.fixture
def settings_enabled() -> Settings:
    reset_settings()
    set_settings_override(_TEST_SETTINGS)
    yield _TEST_SETTINGS
    reset_settings()


@pytest.fixture
def client(settings_enabled: Settings, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    install_gateway_graph_mocks(monkeypatch, settings=settings_enabled)
    yield TestClient(create_app())
    teardown_gateway_graph_mocks()


def test_check_inbound_allows_normal_text(settings_enabled: Settings) -> None:
    result = check_inbound("今天天气怎么样？", settings=settings_enabled)
    assert result.allowed is True
    assert result.reason_code is None


def test_check_inbound_blocks_injection_sample(settings_enabled: Settings) -> None:
    result = check_inbound(INJECTION_TEST_SAMPLE, settings=settings_enabled)
    assert result.allowed is False
    assert result.reason_code == "policy_violation"
    assert result.message


@pytest.mark.parametrize(
    "text",
    [
        HIGH_RISK_TEST_SAMPLE,
        "我想自杀怎么办",
        "怎么盗窃不被发现",
        "怎么撬锁偷东西",
    ],
)
def test_check_inbound_blocks_high_risk_questions(
    settings_enabled: Settings,
    text: str,
) -> None:
    result = check_inbound(text, settings=settings_enabled)
    assert result.allowed is False
    assert result.reason_code == "content_blocked"
    assert result.message == UNSUPPORTED_RISK_MESSAGE


@pytest.mark.parametrize(
    "text",
    [
        POLITICAL_SENSITIVE_TEST_SAMPLE,
        "这个问题有点政治敏感，可以详细分析吗",
        "帮我编领导人的黑料谣言",
    ],
)
def test_check_inbound_blocks_political_sensitive_questions(
    settings_enabled: Settings,
    text: str,
) -> None:
    result = check_inbound(text, settings=settings_enabled)
    assert result.allowed is False
    assert result.reason_code == "content_blocked"
    assert result.message == UNSUPPORTED_POLITICAL_MESSAGE


def test_check_inbound_skipped_when_disabled() -> None:
    disabled = Settings(
        LANGSMITH_API_KEY="lsv2_test",
        OPENAI_API_KEY="sk-test",
        DATABASE_URL=_REQUIRED["DATABASE_URL"],
        GUARDRAILS_ENABLED=False,
    )
    result = check_inbound(INJECTION_TEST_SAMPLE, settings=disabled)
    assert result.allowed is True


def test_high_risk_guard_skipped_when_disabled() -> None:
    disabled = Settings(
        LANGSMITH_API_KEY="lsv2_test",
        OPENAI_API_KEY="sk-test",
        DATABASE_URL=_REQUIRED["DATABASE_URL"],
        GUARDRAILS_ENABLED=False,
    )
    result = check_inbound(HIGH_RISK_TEST_SAMPLE, settings=disabled)
    assert result.allowed is True


def test_optional_hook_can_block_without_rules(settings_enabled: Settings) -> None:
    def hook(text: str) -> GuardResult | None:
        if text == "hook-block-me":
            return GuardResult.block(reason_code="content_blocked", message="Blocked by hook.")
        return None

    register_inbound_hook(hook)
    assert check_inbound("safe", settings=settings_enabled).allowed is True
    blocked = check_inbound("hook-block-me", settings=settings_enabled)
    assert blocked.allowed is False
    assert blocked.reason_code == "content_blocked"


def test_gateway_chat_passes_clean_message(client: TestClient) -> None:
    response = client.post("/internal/chat", json=_VALID_CHAT_PAYLOAD)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")


def test_gateway_chat_rejects_injection_before_stub(client: TestClient) -> None:
    payload = {**_VALID_CHAT_PAYLOAD, "message": INJECTION_TEST_SAMPLE}
    response = client.post("/internal/chat", json=payload)
    assert response.status_code == 400
    body = response.json()
    assert body["detail"]["error"] == "policy_violation"
    assert body["detail"]["message"]


def test_gateway_chat_rejects_high_risk_before_stub(client: TestClient) -> None:
    payload = {**_VALID_CHAT_PAYLOAD, "message": HIGH_RISK_TEST_SAMPLE}
    response = client.post("/internal/chat", json=payload)
    assert response.status_code == 400
    body = response.json()
    assert body["detail"]["error"] == "content_blocked"
    assert body["detail"]["message"] == UNSUPPORTED_RISK_MESSAGE


def test_gateway_chat_rejects_political_sensitive_before_stub(client: TestClient) -> None:
    payload = {**_VALID_CHAT_PAYLOAD, "message": POLITICAL_SENSITIVE_TEST_SAMPLE}
    response = client.post("/internal/chat", json=payload)
    assert response.status_code == 400
    body = response.json()
    assert body["detail"]["error"] == "content_blocked"
    assert body["detail"]["message"] == UNSUPPORTED_POLITICAL_MESSAGE


def test_gateway_chat_allows_injection_when_guardrails_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    disabled = Settings(
        LANGSMITH_API_KEY="lsv2_test",
        OPENAI_API_KEY="sk-test",
        DATABASE_URL=_REQUIRED["DATABASE_URL"],
        GUARDRAILS_ENABLED=False,
    )
    install_gateway_graph_mocks(monkeypatch, settings=disabled)
    client = TestClient(create_app())
    payload = {**_VALID_CHAT_PAYLOAD, "message": INJECTION_TEST_SAMPLE}
    response = client.post("/internal/chat", json=payload)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    teardown_gateway_graph_mocks()
