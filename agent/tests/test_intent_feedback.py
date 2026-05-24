"""Intent feedback helper tests."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from contracts.fallback import FallbackAction, FallbackDecision, FallbackLayer
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
from intent.feedback import (
    feedback_from_correction,
    feedback_from_fallback_conflict,
    feedback_from_path_contract_failure,
    normalize_failure_type,
)


def _memory_query_decision() -> IntentDecision:
    return IntentDecision(
        speech_act=SpeechAct.QUESTION,
        domain=IntentDomain.USER_MEMORY,
        operation=IntentOperation.MEMORY_READ,
        route=IntentRoute.MEMORY_QUERY,
        confidence=0.94,
        risk=IntentRisk.LOW,
        reasons=["first_person_question", "memory_profile_target"],
        evidence=["我是谁"],
    )


def test_feedback_from_user_correction_normalizes_failure_type() -> None:
    feedback = feedback_from_correction(
        original_text="我是谁",
        predicted_route="fact_update",
        corrected_route="memory_query",
        failure_type="false_positive_fact_update",
        trace_id="trace-1",
        thread_id="thread-1",
        user_id="user-1",
        note="用户是在问记忆，不是在写事实",
    )

    assert feedback == IntentFeedback(
        original_text="我是谁",
        predicted_route=IntentRoute.FACT_UPDATE,
        corrected_route=IntentRoute.MEMORY_QUERY,
        failure_type=IntentFeedbackFailureType.FALSE_POSITIVE_FACT_UPDATE,
        trace_id="trace-1",
        thread_id="thread-1",
        user_id="user-1",
        note="用户是在问记忆，不是在写事实",
        source="user",
    )


def test_feedback_rejects_unknown_failure_type_and_blank_text() -> None:
    with pytest.raises(ValueError):
        normalize_failure_type("unknown_failure")

    with pytest.raises(ValidationError):
        IntentFeedback(
            original_text=" ",
            predicted_route="fact_update",
            corrected_route="memory_query",
            failure_type="false_positive_fact_update",
        )


def test_path_contract_failure_maps_to_route_failure_type() -> None:
    feedback = feedback_from_path_contract_failure(
        original_text="我是谁",
        decision=IntentDecision(
            speech_act=SpeechAct.STATEMENT,
            domain=IntentDomain.USER_MEMORY,
            operation=IntentOperation.MEMORY_WRITE,
            route=IntentRoute.FACT_UPDATE,
            confidence=0.94,
            risk=IntentRisk.LOW,
            reasons=["first_person_fact_statement"],
            evidence=["我是谁"],
        ),
        expected_route=IntentRoute.MEMORY_QUERY,
        contract_reason="route_mismatch",
    )

    assert feedback.failure_type == IntentFeedbackFailureType.FALSE_POSITIVE_FACT_UPDATE
    assert feedback.predicted_route == IntentRoute.FACT_UPDATE
    assert feedback.corrected_route == IntentRoute.MEMORY_QUERY
    assert feedback.source == "path_contract"


def test_fallback_conflict_maps_tool_permission_failure() -> None:
    fallback = FallbackDecision(
        layer=FallbackLayer.TOOL,
        reason="tool_not_allowed",
        action=FallbackAction.TOOL_UNAVAILABLE_REPLY,
        original_route="client_action",
        final_route="general_chat",
    )

    feedback = feedback_from_fallback_conflict(original_text="打开订单页", fallback=fallback)

    assert feedback.failure_type == IntentFeedbackFailureType.TOOL_PERMISSION_MISROUTED
    assert feedback.predicted_route == IntentRoute.CLIENT_ACTION
    assert feedback.corrected_route == IntentRoute.GENERAL_CHAT
    assert feedback.source == "fallback"


def test_feedback_to_seed_row_preserves_review_metadata() -> None:
    feedback = feedback_from_correction(
        original_text="我是谁",
        predicted_route="fact_update",
        corrected_route="memory_query",
        failure_type="false_positive_fact_update",
        trace_id="trace-1",
        user_id="user-1",
        note="用户是在问记忆，不是在写事实",
    )

    row = feedback.to_seed_row(
        row_id="intent-feedback-whoami-001",
        expected_intent=_memory_query_decision(),
    )

    assert row["id"] == "intent-feedback-whoami-001"
    assert row["input"] == "我是谁"
    assert row["expected_intent"] == {
        "speech_act": "question",
        "domain": "user_memory",
        "operation": "memory_read",
        "route": "memory_query",
        "risk": "low",
        "reasons": ["first_person_question", "memory_profile_target"],
        "evidence": ["我是谁"],
        "needs_clarification": False,
    }
    assert row["feedback"] == {
        "source": "feedback",
        "failure_type": "false_positive_fact_update",
        "predicted_route": "fact_update",
        "corrected_route": "memory_query",
        "trace_id": "trace-1",
        "user_id": "user-1",
        "note": "用户是在问记忆，不是在写事实",
        "feedback_source": "user",
    }


def test_feedback_to_seed_row_requires_matching_corrected_route() -> None:
    feedback = feedback_from_correction(
        original_text="我是谁",
        predicted_route="fact_update",
        corrected_route="memory_query",
        failure_type="false_positive_fact_update",
    )

    with pytest.raises(ValueError, match="corrected_route"):
        feedback.to_seed_row(
            row_id="intent-feedback-invalid",
            expected_intent=IntentDecision(
                speech_act=SpeechAct.QUESTION,
                domain=IntentDomain.KNOWLEDGE_BASE,
                operation=IntentOperation.KB_RETRIEVE,
                route=IntentRoute.KNOWLEDGE_QUERY,
                confidence=0.9,
                risk=IntentRisk.LOW,
                reasons=["policy_question"],
                evidence=["制度"],
            ),
        )
