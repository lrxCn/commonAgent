"""Fallback manager decisions for the Agent control plane."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from contracts.fallback import FallbackAction, FallbackDecision, FallbackLayer
from contracts.intent import IntentDecision, IntentRoute
from rag.retriever import RagChunk


class _MemoryQueryLike(Protocol):
    missing_reason: str


def intent_fallback_decision(
    decision: IntentDecision | None,
    *,
    conflict_reason: str = "",
    original_route: str = "",
    min_confidence: float = 0.8,
) -> FallbackDecision | None:
    """Return a normalized fallback for low-confidence or conflicting intent."""
    if conflict_reason:
        final_route = _route_value(getattr(decision, "route", "")) if decision else ""
        return FallbackDecision(
            layer=FallbackLayer.INTENT,
            reason=conflict_reason,
            action=FallbackAction.DISABLE_FAST_PATH,
            user_visible=False,
            recovered=True,
            original_route=original_route,
            final_route=final_route,
        )
    if decision is None:
        return FallbackDecision(
            layer=FallbackLayer.INTENT,
            reason="missing_intent_decision",
            action=FallbackAction.CONSERVATIVE_EXECUTOR,
            user_visible=False,
            recovered=True,
            original_route=original_route,
            final_route="general_chat",
        )
    if float(decision.confidence) >= min_confidence:
        return None
    route = _route_value(decision.route)
    action = (
        FallbackAction.ASK_CLARIFICATION
        if bool(decision.needs_clarification) or route == IntentRoute.AMBIGUOUS.value
        else FallbackAction.CONSERVATIVE_EXECUTOR
    )
    return FallbackDecision(
        layer=FallbackLayer.INTENT,
        reason="low_confidence",
        action=action,
        user_visible=action is FallbackAction.ASK_CLARIFICATION,
        recovered=False,
        original_route=original_route,
        final_route=route,
    )


def policy_denied_fallback_decision(
    denied_reason: str,
    *,
    original_route: str = "fact_update",
    final_route: str = "conservative_executor",
) -> FallbackDecision | None:
    """Fallback when Policy Gate rejects a legacy fast path."""
    if not denied_reason:
        return None
    return FallbackDecision(
        layer=FallbackLayer.INTENT,
        reason=denied_reason,
        action=FallbackAction.DISABLE_FAST_PATH,
        user_visible=False,
        recovered=True,
        original_route=original_route,
        final_route=final_route,
    )


def memory_query_fallback_decision(
    result: _MemoryQueryLike,
    *,
    route: str = "memory_query",
) -> FallbackDecision | None:
    """Fallback for memory read queries without reliable evidence."""
    if not result.missing_reason:
        return None
    return FallbackDecision(
        layer=FallbackLayer.MEMORY,
        reason=result.missing_reason,
        action=FallbackAction.HONEST_MISSING_MEMORY,
        user_visible=True,
        recovered=True,
        original_route=route,
        final_route=route,
    )


def rag_quality_fallback_decision(
    *,
    rag_skipped: bool,
    chunks: Sequence[RagChunk] | None,
    threshold: float,
    second_pass: bool = False,
    final: bool = False,
) -> FallbackDecision | None:
    """Fallback for empty or weak RAG retrieval results."""
    if rag_skipped:
        return None
    items = list(chunks or [])
    if not items:
        return FallbackDecision(
            layer=FallbackLayer.RAG,
            reason="rag_empty",
            action=(
                FallbackAction.REPORT_NO_SOURCE
                if final
                else FallbackAction.SECOND_PASS_RETRIEVAL
            ),
            user_visible=final,
            recovered=final,
            original_route="knowledge_query",
            final_route="knowledge_query",
        )
    best_score = max(float(chunk.score) for chunk in items)
    if best_score >= threshold:
        return None
    return FallbackDecision(
        layer=FallbackLayer.RAG,
        reason="rag_weak_hit",
        action=(
            FallbackAction.REPORT_NO_SOURCE
            if final and second_pass
            else FallbackAction.SECOND_PASS_RETRIEVAL
        ),
        user_visible=final and second_pass,
        recovered=not final or second_pass,
        original_route="knowledge_query",
        final_route="knowledge_query",
    )


def tool_fallback_decision(
    reason: str,
    *,
    final_route: str = "general_chat",
    high_risk: bool = False,
) -> FallbackDecision:
    """Fallback for unavailable, unauthorized, or high-risk client tools."""
    return FallbackDecision(
        layer=FallbackLayer.TOOL,
        reason=reason,
        action=FallbackAction.REQUIRE_HITL if high_risk else FallbackAction.TOOL_UNAVAILABLE_REPLY,
        user_visible=True,
        recovered=True,
        original_route="client_action",
        final_route=final_route,
    )


def llm_fallback_decision(reason: str, *, recovered: bool = False) -> FallbackDecision:
    """Fallback for model timeout/provider errors."""
    return FallbackDecision(
        layer=FallbackLayer.LLM,
        reason=reason,
        action=FallbackAction.RETRY_ONCE if not recovered else FallbackAction.TEMPLATE_REPLY,
        user_visible=recovered,
        recovered=recovered,
        original_route="model_call",
        final_route="model_call",
    )


def schema_fallback_decision(reason: str, *, recovered: bool = False) -> FallbackDecision:
    """Fallback for invalid structured output."""
    return FallbackDecision(
        layer=FallbackLayer.SCHEMA,
        reason=reason,
        action=FallbackAction.REPAIR_ONCE if not recovered else FallbackAction.SAFE_ERROR_REPLY,
        user_visible=recovered,
        recovered=recovered,
        original_route="structured_output",
        final_route="structured_output",
    )


def output_guard_fallback_decision(reason: str) -> FallbackDecision:
    """Fallback for blocked outbound content."""
    return FallbackDecision(
        layer=FallbackLayer.OUTPUT_GUARD,
        reason=reason,
        action=FallbackAction.RETRACT_REPLACE_REFUSAL,
        user_visible=True,
        recovered=True,
        original_route="assistant_reply",
        final_route="safe_reply",
    )


def checkpoint_fallback_decision(reason: str) -> FallbackDecision:
    """Fallback for checkpoint/write failures."""
    return FallbackDecision(
        layer=FallbackLayer.CHECKPOINT,
        reason=reason,
        action=FallbackAction.RECOVERABLE_ERROR,
        user_visible=True,
        recovered=False,
        original_route="state_write",
        final_route="recoverable_error",
    )


def _route_value(value: object) -> str:
    return str(getattr(value, "value", value) or "")
