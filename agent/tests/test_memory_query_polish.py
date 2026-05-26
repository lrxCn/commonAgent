"""Tests for memory_query polish contract, validation, and LLM client."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from contracts.llm import ModelUseCase
from contracts.memory_query_polish import (
    MemoryQueryPolishInput,
    build_polish_input,
    validate_polish_output,
)
from infrastructure.llm.gateway import get_llm_gateway
from memory.query import MemoryQueryEvidence, answer_memory_query
from memory.query_polish import (
    build_polish_system_prompt,
    build_polish_user_prompt,
    polish_memory_query_reply,
    set_memory_query_polish_llm,
)
from settings.config import Settings, reset_settings

_REQUIRED_ENV = {
    "LANGSMITH_API_KEY": "lsv2_test",
    "OPENAI_API_KEY": "sk-test",
    "DATABASE_URL": "postgresql://postgres:test@localhost:5432/common_agent",
}


@pytest.fixture(autouse=True)
def _clean_polish() -> None:
    reset_settings()
    set_memory_query_polish_llm(None)
    yield
    set_memory_query_polish_llm(None)
    reset_settings()


def _settings(**extra: object) -> Settings:
    return Settings(**{**_REQUIRED_ENV, **extra})  # type: ignore[arg-type]


def _evidence(
    *,
    field: str = "name",
    value: str = "刘日兴",
    source: str = "memory_profile",
) -> MemoryQueryEvidence:
    return MemoryQueryEvidence(source=source, field=field, value=value, text=f"{field}: {value}")


def _polish_input(**extra: object) -> MemoryQueryPolishInput:
    defaults = {
        "question": "我叫什么",
        "draft_reply": "我记录到你叫刘日兴。",
        "evidence": (_evidence(),),
        "missing_reason": "",
    }
    defaults.update(extra)
    return MemoryQueryPolishInput(**defaults)  # type: ignore[arg-type]


def test_settings_defaults_for_memory_query_polish(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in list(_REQUIRED_ENV) + list(Settings.model_fields):
        monkeypatch.delenv(key, raising=False)
    for key, value in _REQUIRED_ENV.items():
        monkeypatch.setenv(key, value)
    settings = Settings(_env_file=None)
    assert settings.MEMORY_QUERY_POLISH_USE_LLM is False
    assert settings.MEMORY_QUERY_POLISH_MODEL_NAME is None
    assert settings.MEMORY_QUERY_POLISH_MAX_TOKENS == 80
    assert settings.MEMORY_QUERY_POLISH_TIMEOUT_SECONDS == 5


def test_chat_policy_resolves_memory_query_polish_use_case() -> None:
    settings = _settings(
        OPENAI_MODEL_NAME="main-model",
        MEMORY_QUERY_POLISH_MODEL_NAME="polish-small",
        MEMORY_QUERY_POLISH_MAX_TOKENS=72,
        MEMORY_QUERY_POLISH_TIMEOUT_SECONDS=2.5,
    )
    policy = get_llm_gateway(settings).chat_policy(ModelUseCase.MEMORY_QUERY_POLISH)
    assert policy.use_case is ModelUseCase.MEMORY_QUERY_POLISH
    assert (policy.model_name, policy.max_tokens, policy.timeout_seconds) == (
        "polish-small",
        72,
        2.5,
    )


def test_build_polish_input_from_memory_query_result() -> None:
    result = answer_memory_query("我叫什么", user_memories=["用户叫刘日兴"])
    polish_input = build_polish_input("我叫什么", result)
    assert polish_input.draft_reply == result.reply
    assert polish_input.evidence == result.evidence
    assert polish_input.missing_reason == ""


def test_build_polish_prompts_include_draft_and_evidence() -> None:
    polish_input = _polish_input()
    system = build_polish_system_prompt()
    user = build_polish_user_prompt(polish_input)
    assert "不能增删或修改事实" in system
    assert "draft_reply: 我记录到你叫刘日兴。" in user
    assert "value=刘日兴" in user
    assert "missing_reason: none" in user


def test_validate_polish_output_accepts_preserved_evidence() -> None:
    ok, reason = validate_polish_output(
        "我记得你的名字是刘日兴。",
        draft_reply="我记录到你叫刘日兴。",
        evidence=(_evidence(),),
        missing_reason="",
    )
    assert ok is True
    assert reason == ""


def test_validate_polish_output_rejects_missing_evidence_value() -> None:
    ok, reason = validate_polish_output(
        "我记得你的名字是王五。",
        draft_reply="我记录到你叫刘日兴。",
        evidence=(_evidence(),),
        missing_reason="",
    )
    assert ok is False
    assert reason == "missing_evidence_value"


def test_validate_polish_output_rejects_uncertain_phrasing() -> None:
    ok, reason = validate_polish_output(
        "你公司可能在天翔街188号。",
        draft_reply="我记录到你公司的地址是天翔街188号。",
        evidence=(
            _evidence(field="company_address", value="天翔街188号"),
        ),
        missing_reason="",
    )
    assert ok is False
    assert reason == "uncertain_fact_phrasing"


def test_validate_polish_output_rejects_affirmative_fact_when_missing() -> None:
    ok, reason = validate_polish_output(
        "你叫张三。",
        draft_reply="我目前没有可靠记录你的姓名。你可以告诉我你的名字，我之后会按你的授权记住。",
        evidence=(),
        missing_reason="missing_name",
    )
    assert ok is False
    assert reason == "affirmative_fact_when_missing"


def test_validate_polish_output_accepts_honest_missing_reply() -> None:
    ok, reason = validate_polish_output(
        "我这边还没有可靠记录你的姓名。你可以告诉我，我之后会按你的授权记住。",
        draft_reply="我目前没有可靠记录你的姓名。你可以告诉我你的名字，我之后会按你的授权记住。",
        evidence=(),
        missing_reason="missing_name",
    )
    assert ok is True
    assert reason == ""


def test_polish_disabled_returns_deterministic_draft() -> None:
    polish_input = _polish_input()
    result = polish_memory_query_reply(
        polish_input,
        settings=_settings(MEMORY_QUERY_POLISH_USE_LLM=False),
        use_llm=False,
    )
    assert result.reply == polish_input.draft_reply
    assert result.used_llm is False
    assert result.fallback_reason == "disabled"
    assert result.changed is False


def test_polish_llm_success_changes_reply() -> None:
    polish_input = _polish_input()
    mock = MagicMock()
    mock.invoke.return_value = MagicMock(content="我记得你的名字是刘日兴。")
    set_memory_query_polish_llm(mock)

    result = polish_memory_query_reply(
        polish_input,
        settings=_settings(MEMORY_QUERY_POLISH_USE_LLM=True),
        use_llm=True,
    )
    assert result.reply == "我记得你的名字是刘日兴。"
    assert result.used_llm is True
    assert result.fallback_reason == ""
    assert result.changed is True
    mock.invoke.assert_called_once()


def test_polish_llm_exception_falls_back_to_draft() -> None:
    polish_input = _polish_input()

    def _boom(_messages: list[object]) -> str:
        msg = "timeout"
        raise TimeoutError(msg)

    set_memory_query_polish_llm(_boom)
    result = polish_memory_query_reply(
        polish_input,
        settings=_settings(MEMORY_QUERY_POLISH_USE_LLM=True),
        use_llm=True,
    )
    assert result.reply == polish_input.draft_reply
    assert result.used_llm is True
    assert result.fallback_reason == "TimeoutError"
    assert result.changed is False


def test_polish_validation_failure_falls_back_to_draft() -> None:
    polish_input = _polish_input()
    mock = MagicMock()
    mock.invoke.return_value = MagicMock(content="你叫王五。")
    set_memory_query_polish_llm(mock)

    result = polish_memory_query_reply(
        polish_input,
        settings=_settings(MEMORY_QUERY_POLISH_USE_LLM=True),
        use_llm=True,
    )
    assert result.reply == polish_input.draft_reply
    assert result.used_llm is True
    assert result.fallback_reason == "missing_evidence_value"
    assert result.changed is False


def test_polish_missing_memory_can_soften_wording() -> None:
    draft = "我目前没有可靠记录你的姓名。你可以告诉我你的名字，我之后会按你的授权记住。"
    polish_input = MemoryQueryPolishInput(
        question="我叫什么",
        draft_reply=draft,
        evidence=(),
        missing_reason="missing_name",
    )
    mock = MagicMock()
    mock.invoke.return_value = MagicMock(
        content="我这边还没有可靠记录你的姓名。你可以告诉我，我之后会按你的授权记住。"
    )
    set_memory_query_polish_llm(mock)

    result = polish_memory_query_reply(
        polish_input,
        settings=_settings(MEMORY_QUERY_POLISH_USE_LLM=True),
        use_llm=True,
    )
    assert result.reply.startswith("我这边还没有可靠记录你的姓名")
    assert result.used_llm is True
    assert result.fallback_reason == ""
    assert result.changed is True
