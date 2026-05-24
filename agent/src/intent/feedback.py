"""Feedback helpers for the intent control-plane eval loop."""

from __future__ import annotations

from contracts.fallback import FallbackDecision
from contracts.intent import (
    IntentDecision,
    IntentFeedback,
    IntentFeedbackFailureType,
    IntentRoute,
)

_FALLBACK_FAILURE_BY_REASON = {
    "low_confidence": IntentFeedbackFailureType.LOW_CONFIDENCE_MISROUTED,
    "tool_not_allowed": IntentFeedbackFailureType.TOOL_PERMISSION_MISROUTED,
    "tool_unavailable": IntentFeedbackFailureType.TOOL_PERMISSION_MISROUTED,
    "rag_empty": IntentFeedbackFailureType.FALLBACK_MISSING,
    "rag_weak_hit": IntentFeedbackFailureType.FALLBACK_MISSING,
}


def normalize_failure_type(value: str | IntentFeedbackFailureType) -> IntentFeedbackFailureType:
    """Return a stable feedback failure type or raise for unknown labels."""
    return IntentFeedbackFailureType(str(getattr(value, "value", value)))


def feedback_from_correction(
    *,
    original_text: str,
    predicted_route: str | IntentRoute,
    corrected_route: str | IntentRoute,
    failure_type: str | IntentFeedbackFailureType,
    trace_id: str | None = None,
    thread_id: str | None = None,
    user_id: str | None = None,
    note: str = "",
    source: str = "user",
) -> IntentFeedback:
    """Build a feedback row from user or human-review route correction."""
    return IntentFeedback(
        original_text=original_text,
        predicted_route=IntentRoute(str(getattr(predicted_route, "value", predicted_route))),
        corrected_route=IntentRoute(str(getattr(corrected_route, "value", corrected_route))),
        failure_type=normalize_failure_type(failure_type),
        trace_id=trace_id,
        thread_id=thread_id,
        user_id=user_id,
        note=note,
        source=source,
    )


def feedback_from_path_contract_failure(
    *,
    original_text: str,
    decision: IntentDecision,
    expected_route: str | IntentRoute,
    contract_reason: str,
    trace_id: str | None = None,
    thread_id: str | None = None,
    user_id: str | None = None,
) -> IntentFeedback:
    """Convert a path contract failure into a route-correction feedback item."""
    corrected = IntentRoute(str(getattr(expected_route, "value", expected_route)))
    return IntentFeedback(
        original_text=original_text,
        predicted_route=decision.route,
        corrected_route=corrected,
        failure_type=_route_failure_type(
            predicted_route=IntentRoute(decision.route),
            corrected_route=corrected,
        ),
        trace_id=trace_id,
        thread_id=thread_id,
        user_id=user_id,
        note=contract_reason,
        source="path_contract",
    )


def feedback_from_fallback_conflict(
    *,
    original_text: str,
    fallback: FallbackDecision,
    trace_id: str | None = None,
    thread_id: str | None = None,
    user_id: str | None = None,
) -> IntentFeedback:
    """Convert a fallback conflict into feedback for later eval coverage."""
    return IntentFeedback(
        original_text=original_text,
        predicted_route=_route_or_ambiguous(fallback.original_route),
        corrected_route=_route_or_none(fallback.final_route),
        failure_type=_FALLBACK_FAILURE_BY_REASON.get(
            str(fallback.reason),
            IntentFeedbackFailureType.FALLBACK_MISSING,
        ),
        trace_id=trace_id,
        thread_id=thread_id,
        user_id=user_id,
        note=str(fallback.reason),
        source="fallback",
    )


def _route_failure_type(
    *,
    predicted_route: IntentRoute,
    corrected_route: IntentRoute,
) -> IntentFeedbackFailureType:
    if predicted_route is IntentRoute.FACT_UPDATE:
        return IntentFeedbackFailureType.FALSE_POSITIVE_FACT_UPDATE
    if corrected_route is IntentRoute.FACT_UPDATE:
        return IntentFeedbackFailureType.FALSE_NEGATIVE_FACT_UPDATE
    if predicted_route is IntentRoute.MEMORY_QUERY:
        return IntentFeedbackFailureType.FALSE_POSITIVE_MEMORY_QUERY
    if corrected_route is IntentRoute.MEMORY_QUERY:
        return IntentFeedbackFailureType.FALSE_NEGATIVE_MEMORY_QUERY
    if predicted_route is IntentRoute.KNOWLEDGE_QUERY or corrected_route is IntentRoute.KNOWLEDGE_QUERY:
        return IntentFeedbackFailureType.WRONG_KNOWLEDGE_QUERY
    if predicted_route is IntentRoute.CLIENT_ACTION or corrected_route is IntentRoute.CLIENT_ACTION:
        return IntentFeedbackFailureType.WRONG_CLIENT_ACTION
    return IntentFeedbackFailureType.LOW_CONFIDENCE_MISROUTED


def _route_or_ambiguous(value: str) -> IntentRoute:
    try:
        return IntentRoute(value)
    except ValueError:
        return IntentRoute.AMBIGUOUS


def _route_or_none(value: str) -> IntentRoute | None:
    try:
        return IntentRoute(value)
    except ValueError:
        return None
