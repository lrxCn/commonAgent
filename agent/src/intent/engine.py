"""Pure deterministic intent engine entrypoint."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from contracts.intent import IntentDecision
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
