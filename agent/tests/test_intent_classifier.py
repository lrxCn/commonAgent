"""Tests for structured LLM intent classifier candidates."""

from __future__ import annotations

import json

import pytest

from contracts.intent import IntentOperation, IntentRoute
from contracts.llm import ModelUseCase
from gateway.schemas import ToolSpec
from intent.classifier import (
    classify_intent_with_llm,
    parse_intent_decision,
    set_intent_classifier_llm,
    should_call_intent_classifier,
)
from intent.conflicts import check_intent_conflicts
from intent.rules import decide_with_rules
from intent.signals import extract_signals
from settings.config import Settings, reset_settings

_REQUIRED_ENV = {
    "LANGSMITH_API_KEY": "lsv2_test",
    "OPENAI_API_KEY": "sk-test",
    "DATABASE_URL": "postgresql://postgres:test@localhost:5432/common_agent",
}


@pytest.fixture(autouse=True)
def _clean_classifier() -> None:
    reset_settings()
    set_intent_classifier_llm(None)
    yield
    set_intent_classifier_llm(None)
    reset_settings()


def _settings(**extra: object) -> Settings:
    return Settings(**{**_REQUIRED_ENV, **extra})  # type: ignore[arg-type]


def _decision_json(**extra: object) -> str:
    payload = {
        "speech_act": "question",
        "domain": "knowledge_base",
        "operation": "kb_retrieve",
        "route": "knowledge_query",
        "confidence": 0.84,
        "risk": "low",
        "reasons": ["model_structured_candidate"],
        "evidence": ["报销制度"],
        "needs_clarification": False,
    }
    payload.update(extra)
    return json.dumps(payload, ensure_ascii=False)


def test_classifier_uses_structured_output_and_gateway_policy() -> None:
    settings = _settings(
        INTENT_CLASSIFIER_MODEL_NAME="intent-small",
        INTENT_CLASSIFIER_MAX_TOKENS=111,
        INTENT_CLASSIFIER_TIMEOUT_SECONDS=2.5,
    )
    seen: dict[str, object] = {}

    class FakeLlm:
        def invoke(self, messages: object) -> object:
            seen["messages"] = messages
            return type("Response", (), {"content": _decision_json()})()

    class FakeGateway:
        def chat_model(self, use_case: ModelUseCase) -> FakeLlm:
            seen["use_case"] = use_case
            return FakeLlm()

    result = classify_intent_with_llm(
        "报销制度是什么",
        settings=settings,
        gateway=FakeGateway(),  # type: ignore[arg-type]
    )

    assert result.decision.route == IntentRoute.KNOWLEDGE_QUERY
    assert result.decision.operation == IntentOperation.KB_RETRIEVE
    assert result.fallback is False
    assert seen["use_case"] is ModelUseCase.INTENT_CLASSIFIER
    policy = __import__("infrastructure.llm.gateway", fromlist=["get_llm_gateway"]).get_llm_gateway(
        settings
    ).chat_policy(ModelUseCase.INTENT_CLASSIFIER)
    assert (policy.model_name, policy.max_tokens, policy.timeout_seconds) == (
        "intent-small",
        111,
        2.5,
    )


def test_classifier_repairs_invalid_schema_once() -> None:
    calls: list[object] = []

    def fake_llm(_messages: list[object]) -> str:
        calls.append(_messages)
        if len(calls) == 1:
            return '{"route": "knowledge_query"}'
        return _decision_json()

    set_intent_classifier_llm(fake_llm)

    result = classify_intent_with_llm("报销制度是什么", settings=_settings())

    assert result.decision.route == IntentRoute.KNOWLEDGE_QUERY
    assert result.repaired is True
    assert result.fallback is False
    assert len(calls) == 2


def test_classifier_schema_invalid_after_repair_falls_back() -> None:
    set_intent_classifier_llm(lambda _messages: "not json")

    result = classify_intent_with_llm("帮我写一段开场白", settings=_settings())

    assert result.fallback is True
    assert result.repaired is True
    assert result.fallback_reason == "schema_invalid"
    assert result.decision.route == IntentRoute.GENERAL_CHAT
    assert result.decision.confidence <= 0.2


def test_classifier_timeout_falls_back_safely() -> None:
    class TimeoutLlm:
        def invoke(self, _messages: object) -> object:
            raise TimeoutError("slow")

    class FakeGateway:
        def chat_model(self, use_case: ModelUseCase) -> TimeoutLlm:
            assert use_case is ModelUseCase.INTENT_CLASSIFIER
            return TimeoutLlm()

    result = classify_intent_with_llm(
        "报销制度是什么",
        settings=_settings(),
        gateway=FakeGateway(),  # type: ignore[arg-type]
    )

    assert result.fallback is True
    assert result.fallback_reason == "timeout"
    assert result.decision.operation in {
        IntentOperation.ANSWER,
        IntentOperation.CLARIFY,
        IntentOperation.REJECT,
    }


def test_conflict_check_rejects_question_memory_write_candidate() -> None:
    signals = extract_signals("我的生日是什么？")
    candidate = parse_intent_decision(
        _decision_json(
            speech_act="question",
            domain="user_memory",
            operation="memory_write",
            route="fact_update",
            risk="high",
            reasons=["bad_model_candidate"],
            evidence=["生日"],
        )
    )

    conflict = check_intent_conflicts(
        signals=signals,
        candidate=candidate,
        rule_decision=decide_with_rules(signals),
    )

    assert conflict.has_conflict is True
    assert "question_memory_write_conflict" in conflict.reasons
    assert conflict.fallback_route == IntentRoute.MEMORY_QUERY


def test_conflicting_classifier_candidate_returns_safe_fallback() -> None:
    set_intent_classifier_llm(
        lambda _messages: _decision_json(
            speech_act="question",
            domain="user_memory",
            operation="memory_write",
            route="fact_update",
            risk="high",
            reasons=["bad_model_candidate"],
            evidence=["名字"],
        )
    )

    result = classify_intent_with_llm("我的名字是什么？", settings=_settings())

    assert result.fallback is True
    assert result.decision.route == IntentRoute.MEMORY_QUERY
    assert result.decision.operation == IntentOperation.MEMORY_READ
    assert result.conflict.has_conflict is True


def test_client_action_candidate_without_allowed_tool_conflicts() -> None:
    set_intent_classifier_llm(
        lambda _messages: _decision_json(
            speech_act="command",
            domain="client_tool",
            operation="client_action",
            route="client_action",
            risk="medium",
            reasons=["tool_command"],
            evidence=["pageA"],
        )
    )

    result = classify_intent_with_llm("打开 pageA", settings=_settings(), tools_context=[])

    assert result.fallback is True
    assert result.decision.route == IntentRoute.GENERAL_CHAT
    assert "client_action_without_allowed_tool" in result.conflict.reasons


def test_should_call_classifier_for_low_confidence_rules_only() -> None:
    high = decide_with_rules(extract_signals("我叫张三"))
    low = decide_with_rules(extract_signals("帮我写一段周会开场白"))

    assert should_call_intent_classifier(rule_decision=high, signals=extract_signals("我叫张三")) is False
    assert should_call_intent_classifier(
        rule_decision=low,
        signals=extract_signals("帮我写一段周会开场白"),
    ) is True


def test_client_action_candidate_with_allowed_tool_can_remain_candidate() -> None:
    set_intent_classifier_llm(
        lambda _messages: _decision_json(
            speech_act="command",
            domain="client_tool",
            operation="client_action",
            route="client_action",
            risk="low",
            reasons=["tool_command"],
            evidence=["pageA"],
        )
    )

    result = classify_intent_with_llm(
        "打开 pageA",
        settings=_settings(),
        tools_context=[ToolSpec(name="jumpPage", description="Navigate.")],
    )

    assert result.fallback is False
    assert result.candidate.route == IntentRoute.CLIENT_ACTION
