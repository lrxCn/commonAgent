"""Policy Gate coverage for fact_update fast path admission."""

from __future__ import annotations

import pytest

from contracts.intent import (
    IntentDecision,
    IntentDomain,
    IntentOperation,
    IntentRisk,
    IntentRoute,
    SpeechAct,
)
from intent import classify_intent
from intent.policy import decide_fast_path_policy_for_message


def _decision(**overrides: object) -> IntentDecision:
    payload = {
        "speech_act": SpeechAct.STATEMENT,
        "domain": IntentDomain.USER_MEMORY,
        "operation": IntentOperation.MEMORY_WRITE,
        "route": IntentRoute.FACT_UPDATE,
        "confidence": 0.94,
        "risk": IntentRisk.LOW,
        "reasons": ["first_person_fact_statement", "explicit_fact_value"],
        "evidence": ["我叫张三"],
    }
    payload.update(overrides)
    return IntentDecision(**payload)


def test_policy_allows_high_confidence_explicit_memory_write() -> None:
    policy = decide_fast_path_policy_for_message(_decision(), "我叫张三")

    assert policy.fast_path_allowed is True
    assert policy.denied_reason == ""
    assert policy.to_trace_dict() == {
        "policy.fast_path_allowed": True,
        "policy.denied_reason": "",
    }


@pytest.mark.parametrize(
    ("message", "decision", "reason"),
    [
        (
            "我叫张三吗？",
            _decision(speech_act=SpeechAct.QUESTION),
            "speech_act_not_statement",
        ),
        (
            "我叫张三",
            _decision(operation=IntentOperation.MEMORY_READ),
            "operation_not_memory_write",
        ),
        (
            "我叫张三",
            _decision(route=IntentRoute.GENERAL_CHAT),
            "route_not_fact_update",
        ),
        ("我叫张三", _decision(confidence=0.89), "confidence_below_0_9"),
        ("我叫张三", _decision(risk=IntentRisk.MEDIUM), "risk_not_low"),
        ("我是张三吗？", _decision(), "question_signal"),
        ("我叫", _decision(), "missing_explicit_value"),
        ("我是张三", _decision(), "missing_explicit_attribute"),
    ],
)
def test_policy_denies_any_failed_fast_path_condition(
    message: str,
    decision: IntentDecision,
    reason: str,
) -> None:
    policy = decide_fast_path_policy_for_message(decision, message)

    assert policy.fast_path_allowed is False
    assert policy.denied_reason == reason


@pytest.mark.parametrize(
    "message",
    [
        "我是谁",
        "我叫什么",
        "我的名字是什么",
        "我公司在哪",
        "我喜欢什么",
        "我是做什么的",
        "你知道我是谁吗",
    ],
)
def test_required_memory_questions_are_not_fast_path_allowed(message: str) -> None:
    decision = classify_intent(message)
    policy = decide_fast_path_policy_for_message(decision, message)

    assert decision.route == IntentRoute.MEMORY_QUERY
    assert decision.operation == IntentOperation.MEMORY_READ
    assert policy.fast_path_allowed is False
    assert policy.denied_reason != ""
