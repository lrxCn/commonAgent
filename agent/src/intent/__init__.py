"""Deterministic intent control-plane API."""

from intent.classifier import (
    IntentClassifierResult,
    classify_intent_with_llm,
    set_intent_classifier_llm,
    should_call_intent_classifier,
)
from intent.engine import classify_intent, turn_type_decision_from_intent
from intent.conflicts import IntentConflictCheck, check_intent_conflicts
from intent.fallback import (
    checkpoint_fallback_decision,
    intent_fallback_decision,
    llm_fallback_decision,
    memory_query_fallback_decision,
    output_guard_fallback_decision,
    policy_denied_fallback_decision,
    rag_quality_fallback_decision,
    schema_fallback_decision,
    tool_fallback_decision,
)
from intent.feedback import (
    feedback_from_correction,
    feedback_from_fallback_conflict,
    feedback_from_path_contract_failure,
    normalize_failure_type,
)
from intent.policy import (
    PolicyDecision,
    decide_fast_path_policy,
    decide_fast_path_policy_for_message,
)
from intent.rules import decide_with_rules
from intent.signals import IntentSignals, extract_signals, normalize_text

__all__ = [
    "IntentClassifierResult",
    "IntentConflictCheck",
    "IntentSignals",
    "PolicyDecision",
    "checkpoint_fallback_decision",
    "classify_intent",
    "turn_type_decision_from_intent",
    "classify_intent_with_llm",
    "check_intent_conflicts",
    "decide_with_rules",
    "decide_fast_path_policy",
    "decide_fast_path_policy_for_message",
    "extract_signals",
    "feedback_from_correction",
    "feedback_from_fallback_conflict",
    "feedback_from_path_contract_failure",
    "intent_fallback_decision",
    "llm_fallback_decision",
    "memory_query_fallback_decision",
    "normalize_failure_type",
    "normalize_text",
    "output_guard_fallback_decision",
    "policy_denied_fallback_decision",
    "rag_quality_fallback_decision",
    "schema_fallback_decision",
    "set_intent_classifier_llm",
    "should_call_intent_classifier",
    "tool_fallback_decision",
]
