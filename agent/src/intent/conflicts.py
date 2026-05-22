"""Conflict checks for intent candidates before policy gating."""

from __future__ import annotations

from dataclasses import dataclass

from contracts.intent import IntentDecision, IntentOperation, IntentRoute, IntentRisk
from intent.signals import IntentSignals


@dataclass(frozen=True)
class IntentConflictCheck:
    """Conflict result for rule/model decisions and extracted signals."""

    has_conflict: bool
    reasons: tuple[str, ...] = ()
    fallback_route: IntentRoute | None = None

    @property
    def fallback_reason(self) -> str:
        """Return a stable fallback reason for traces and classifier results."""
        return "|".join(self.reasons)


def check_intent_conflicts(
    *,
    signals: IntentSignals,
    candidate: IntentDecision,
    rule_decision: IntentDecision | None = None,
) -> IntentConflictCheck:
    """Detect high-risk disagreement before any intent candidate can execute."""
    reasons: list[str] = []

    if _question_requests_memory_write(signals, candidate):
        reasons.append("question_memory_write_conflict")
    if _client_action_without_allowed_tool(signals, candidate):
        reasons.append("client_action_without_allowed_tool")
    if _safety_signal_not_refused(signals, candidate):
        reasons.append("safety_signal_route_conflict")
    if _knowledge_signal_memory_write(signals, candidate):
        reasons.append("knowledge_signal_memory_write_conflict")
    if rule_decision is not None and _high_confidence_route_disagreement(rule_decision, candidate):
        reasons.append("rule_model_route_conflict")
    if candidate.risk == IntentRisk.HIGH.value and candidate.route != IntentRoute.SAFETY_REFUSAL.value:
        reasons.append("high_risk_non_refusal")

    if not reasons:
        return IntentConflictCheck(has_conflict=False)
    return IntentConflictCheck(
        has_conflict=True,
        reasons=tuple(dict.fromkeys(reasons)),
        fallback_route=_fallback_route(signals, candidate),
    )


def _question_requests_memory_write(signals: IntentSignals, candidate: IntentDecision) -> bool:
    return signals.is_question and candidate.operation == IntentOperation.MEMORY_WRITE.value


def _client_action_without_allowed_tool(signals: IntentSignals, candidate: IntentDecision) -> bool:
    return (
        candidate.operation == IntentOperation.CLIENT_ACTION.value
        and not signals.has_allowed_client_tool
    )


def _safety_signal_not_refused(signals: IntentSignals, candidate: IntentDecision) -> bool:
    return bool(signals.safety_reasons) and candidate.route != IntentRoute.SAFETY_REFUSAL.value


def _knowledge_signal_memory_write(signals: IntentSignals, candidate: IntentDecision) -> bool:
    return (
        signals.has_knowledge_signal
        and candidate.operation == IntentOperation.MEMORY_WRITE.value
    )


def _high_confidence_route_disagreement(
    rule_decision: IntentDecision,
    candidate: IntentDecision,
) -> bool:
    return (
        rule_decision.confidence >= 0.9
        and rule_decision.route != candidate.route
        and (
            rule_decision.route
            in {
                IntentRoute.FACT_UPDATE.value,
                IntentRoute.MEMORY_QUERY.value,
                IntentRoute.SAFETY_REFUSAL.value,
                IntentRoute.CLIENT_ACTION.value,
            }
            or candidate.operation
            in {
                IntentOperation.MEMORY_WRITE.value,
                IntentOperation.CLIENT_ACTION.value,
                IntentOperation.REJECT.value,
            }
        )
    )


def _fallback_route(signals: IntentSignals, candidate: IntentDecision) -> IntentRoute:
    if signals.safety_reasons:
        return IntentRoute.SAFETY_REFUSAL
    if signals.is_question and candidate.operation == IntentOperation.MEMORY_WRITE.value:
        return IntentRoute.MEMORY_QUERY
    if candidate.operation == IntentOperation.CLIENT_ACTION.value and not signals.has_allowed_client_tool:
        return IntentRoute.GENERAL_CHAT
    return IntentRoute.AMBIGUOUS
