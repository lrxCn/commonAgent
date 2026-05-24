"""Policy gate decisions for intent-driven fast paths."""

from __future__ import annotations

from dataclasses import dataclass

from contracts.intent import (
    IntentDecision,
    IntentOperation,
    IntentRisk,
    IntentRoute,
    SpeechAct,
)
from intent.signals import IntentSignals, extract_signals


@dataclass(frozen=True)
class PolicyDecision:
    """Control-plane decision for graph fast paths."""

    fast_path_allowed: bool
    denied_reason: str = ""

    def to_trace_dict(self) -> dict[str, object]:
        """Flatten to stable trace metadata keys."""
        return {
            "policy.fast_path_allowed": self.fast_path_allowed,
            "policy.denied_reason": self.denied_reason,
        }


def decide_fast_path_policy(
    decision: IntentDecision | None,
    *,
    signals: IntentSignals,
) -> PolicyDecision:
    """Return whether the current turn may enter the fact_update fast path."""
    if decision is None:
        return PolicyDecision(False, "missing_intent_decision")

    checks = [
        (_value(decision.speech_act) == SpeechAct.STATEMENT.value, "speech_act_not_statement"),
        (_value(decision.operation) == IntentOperation.MEMORY_WRITE.value, "operation_not_memory_write"),
        (_value(decision.route) == IntentRoute.FACT_UPDATE.value, "route_not_fact_update"),
        (float(decision.confidence) >= 0.9, "confidence_below_0_9"),
        (_value(decision.risk) == IntentRisk.LOW.value, "risk_not_low"),
        (not bool(signals.is_question), "question_signal"),
        (bool(signals.fact_attributes), "missing_explicit_attribute"),
        (bool(signals.has_explicit_value), "missing_explicit_value"),
    ]
    for passed, reason in checks:
        if not passed:
            return PolicyDecision(False, reason)
    return PolicyDecision(True, "")


def decide_fast_path_policy_for_message(
    decision: IntentDecision | None,
    message: str,
    *,
    tools_context: object = None,
) -> PolicyDecision:
    """Compatibility helper for tests and non-graph callers."""
    signals = extract_signals(message, tools_context=tools_context)  # type: ignore[arg-type]
    return decide_fast_path_policy(decision, signals=signals)


def _value(value: object) -> str:
    return str(getattr(value, "value", value))
