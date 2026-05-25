"""Pure deterministic intent engine entrypoint."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from contracts.intent import IntentDecision
from contracts.routing import TurnTypeDecision
from gateway.schemas import ToolSpec
from intent.rules import decide_with_rules
from intent.signals import extract_signals


def classify_intent(
    message: str,
    *,
    tools_context: Sequence[ToolSpec | dict[str, Any]] | None = None,
) -> IntentDecision:
    """
    Classify user intent using normalize -> signals -> deterministic rules.

    This is intentionally pure logic for control-plane phase 1: no LLM calls,
    no graph state reads, and no side effects.
    """
    return decide_with_rules(extract_signals(message, tools_context=tools_context))


def turn_type_decision_from_intent(intent_decision: IntentDecision) -> TurnTypeDecision:
    """
    Derive a legacy-compatible TurnTypeDecision from an IntentDecision.

    Single authority contract: only ``IntentDecision.turn_type`` and
    ``IntentDecision.turn_type_reason`` are read. No LLM, graph state,
    checkpoint, mem0, or legacy ``rag.intent`` rules are invoked.
    """
    return TurnTypeDecision(
        turn_type=intent_decision.turn_type,
        reason=intent_decision.turn_type_reason,
    )
