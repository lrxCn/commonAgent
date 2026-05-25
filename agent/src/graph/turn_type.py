"""Legacy-compatible turn_type adapter for graph routing metadata.

``classify_turn_type()`` delegates to the intent control plane and returns a
``TurnTypeDecision`` derived from ``IntentDecision``. It is not an independent
classifier; ``rag.intent`` helpers remain available to rewrite/router locally.
"""

from __future__ import annotations

from typing import Sequence

from contracts.routing import TurnType, TurnTypeDecision
from gateway.schemas import ToolSpec
from intent.engine import classify_intent, turn_type_decision_from_intent

__all__ = ["TurnType", "TurnTypeDecision", "classify_turn_type"]


def _text(value: str | None) -> str:
    return (value or "").strip()


def classify_turn_type(
    message: str,
    *,
    rewritten_query: str | None = None,
    tools_context: Sequence[ToolSpec | dict] | None = None,
) -> TurnTypeDecision:
    """Return a legacy ``TurnTypeDecision`` from the single intent authority."""
    text = _text(message)
    rewritten = _text(rewritten_query)
    if not text and not rewritten:
        return TurnTypeDecision(TurnType.GENERAL_CHAT, "empty")

    classify_text = text or rewritten
    intent_decision = classify_intent(classify_text, tools_context=tools_context)
    return turn_type_decision_from_intent(intent_decision)
