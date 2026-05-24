"""Intent control-plane contract tests."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from contracts.intent import (
    IntentDecision,
    IntentDomain,
    IntentFeedback,
    IntentFeedbackFailureType,
    IntentOperation,
    IntentRisk,
    IntentRoute,
    SpeechAct,
)
from contracts.routing import TurnType


def test_intent_enums_define_control_plane_dimensions() -> None:
    assert SpeechAct.QUESTION.value == "question"
    assert IntentDomain.USER_MEMORY.value == "user_memory"
    assert IntentOperation.MEMORY_READ.value == "memory_read"
    assert IntentRoute.MEMORY_QUERY.value == "memory_query"
    assert IntentRisk.LOW.value == "low"


def test_intent_decision_serializes_to_trace_dict_with_turn_type_compatibility() -> None:
    decision = IntentDecision(
        speech_act=SpeechAct.QUESTION,
        domain=IntentDomain.USER_MEMORY,
        operation=IntentOperation.MEMORY_READ,
        route=IntentRoute.MEMORY_QUERY,
        confidence=0.94,
        risk=IntentRisk.LOW,
        reasons=["first_person_question", "memory_profile_target"],
        evidence=["我是谁"],
        needs_clarification=False,
    )

    payload = decision.to_trace_dict()

    assert decision.turn_type is TurnType.MEMORY_QUERY
    assert decision.turn_type_reason == "first_person_question"
    assert payload == {
        "speech_act": "question",
        "domain": "user_memory",
        "operation": "memory_read",
        "route": "memory_query",
        "confidence": 0.94,
        "risk": "low",
        "reasons": ["first_person_question", "memory_profile_target"],
        "evidence": ["我是谁"],
        "needs_clarification": False,
        "turn_type": "memory_query",
        "turn_type_reason": "first_person_question",
    }


@pytest.mark.parametrize(
    ("route", "turn_type"),
    [
        (IntentRoute.FACT_UPDATE, TurnType.FACT_UPDATE),
        (IntentRoute.MEMORY_QUERY, TurnType.MEMORY_QUERY),
        (IntentRoute.KNOWLEDGE_QUERY, TurnType.KNOWLEDGE_QUERY),
        (IntentRoute.CLIENT_ACTION, TurnType.CLIENT_ACTION),
        (IntentRoute.CHITCHAT, TurnType.CHITCHAT),
        (IntentRoute.AMBIGUOUS, TurnType.AMBIGUOUS),
        (IntentRoute.GENERAL_CHAT, TurnType.GENERAL_CHAT),
        (IntentRoute.SAFETY_REFUSAL, TurnType.SAFETY_REFUSAL),
    ],
)
def test_intent_route_maps_to_legacy_turn_type(route: IntentRoute, turn_type: TurnType) -> None:
    decision = IntentDecision(
        speech_act=SpeechAct.UNCLEAR,
        domain=IntentDomain.UNKNOWN,
        operation=IntentOperation.CLARIFY,
        route=route,
        confidence=0.5,
        risk=IntentRisk.MEDIUM,
        reasons=["test_reason"],
        evidence=["input"],
        needs_clarification=True,
    )

    assert decision.turn_type is turn_type


def test_intent_decision_rejects_invalid_confidence_and_extra_fields() -> None:
    with pytest.raises(ValidationError):
        IntentDecision(
            speech_act="question",
            domain="user_memory",
            operation="memory_read",
            route="memory_query",
            confidence=1.2,
            risk="low",
        )

    with pytest.raises(ValidationError):
        IntentDecision(
            speech_act="question",
            domain="user_memory",
            operation="memory_read",
            route="memory_query",
            confidence=0.8,
            risk="low",
            unexpected=True,
        )


def test_intent_decision_rejects_blank_reason_or_evidence() -> None:
    with pytest.raises(ValidationError):
        IntentDecision(
            speech_act="question",
            domain="user_memory",
            operation="memory_read",
            route="memory_query",
            confidence=0.8,
            risk="low",
            reasons=[" "],
            evidence=["我是谁"],
        )


def test_intent_feedback_serializes_for_eval_loop() -> None:
    feedback = IntentFeedback(
        original_text="我是谁",
        predicted_route=IntentRoute.FACT_UPDATE,
        corrected_route=IntentRoute.MEMORY_QUERY,
        failure_type=IntentFeedbackFailureType.FALSE_POSITIVE_FACT_UPDATE,
        trace_id="trace-1",
        thread_id="thread-1",
        user_id="user-1",
        note="用户是在问记忆，不是在写事实",
    )

    assert feedback.model_dump(mode="json") == {
        "original_text": "我是谁",
        "predicted_route": "fact_update",
        "corrected_route": "memory_query",
        "failure_type": "false_positive_fact_update",
        "trace_id": "trace-1",
        "thread_id": "thread-1",
        "user_id": "user-1",
        "note": "用户是在问记忆，不是在写事实",
        "source": "user",
    }
