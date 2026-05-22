"""Tests for the chitchat lightweight executor."""

from __future__ import annotations

import pytest

from contracts.llm import ModelUseCase
from graph.chitchat_executor import chitchat_reply, set_chitchat_llm
from infrastructure.llm.gateway import get_llm_gateway
from settings.config import Settings, reset_settings, set_settings_override

_REQUIRED_ENV = {
    "LANGSMITH_API_KEY": "lsv2_test",
    "OPENAI_API_KEY": "sk-test",
    "DATABASE_URL": "postgresql://postgres:test@localhost:5432/common_agent",
}


@pytest.fixture(autouse=True)
def _clean() -> None:
    set_chitchat_llm(None)
    reset_settings()
    set_settings_override(Settings(**_REQUIRED_ENV))  # type: ignore[arg-type]
    yield
    set_chitchat_llm(None)
    reset_settings()


def test_chitchat_uses_template_by_default() -> None:
    result = chitchat_reply("谢谢")
    assert result["executor"] == "template_executor"
    assert result["reply"] == "不客气。"


def test_chitchat_uses_small_llm_when_enabled() -> None:
    set_settings_override(
        Settings(**_REQUIRED_ENV, CHITCHAT_USE_LLM=True)  # type: ignore[arg-type]
    )
    calls: list[str] = []
    set_chitchat_llm(lambda prompt: calls.append(prompt) or "你好呀。")

    result = chitchat_reply("你好")

    assert result["executor"] == "small_chat_executor"
    assert result["reply"] == "你好呀。"
    assert len(calls) == 1


def test_chitchat_falls_back_to_template_when_llm_errors() -> None:
    set_settings_override(
        Settings(**_REQUIRED_ENV, CHITCHAT_USE_LLM=True)  # type: ignore[arg-type]
    )

    def boom(_prompt: str) -> str:
        raise RuntimeError("boom")

    set_chitchat_llm(boom)
    result = chitchat_reply("谢谢")

    assert result["executor"] == "template_executor"
    assert result["reply"] == "不客气。"


def test_chitchat_uses_gateway_policy_from_settings() -> None:
    settings = Settings(
        **_REQUIRED_ENV,
        CHITCHAT_MODEL_NAME="chitchat-model",
        CHITCHAT_MAX_TOKENS=17,
        CHITCHAT_TIMEOUT_SECONDS=2.0,
    )  # type: ignore[arg-type]

    policy = get_llm_gateway(settings).chat_policy(ModelUseCase.CHITCHAT)

    assert policy.model_name == "chitchat-model"
    assert policy.max_tokens == 17
    assert policy.timeout_seconds == 2.0
