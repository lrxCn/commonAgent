"""Agent-level fallback manager contract and strategy matrix."""

from __future__ import annotations

from contracts.fallback import FallbackAction, FallbackDecision, FallbackLayer
from contracts.intent import (
    IntentDecision,
    IntentDomain,
    IntentOperation,
    IntentRisk,
    IntentRoute,
    SpeechAct,
)
from infrastructure.langsmith import event_to_metadata
from contracts.events import ObservabilityEvent, ObservabilityEventType
from intent.fallback import (
    intent_fallback_decision,
    llm_fallback_decision,
    memory_query_fallback_decision,
    output_guard_fallback_decision,
    rag_quality_fallback_decision,
    schema_fallback_decision,
    tool_fallback_decision,
)
from memory.query import answer_memory_query
from observability.path_contract import path_metrics_metadata, record_fallback_decision
from rag.retriever import RagChunk


def _decision(**overrides: object) -> IntentDecision:
    payload: dict[str, object] = {
        "speech_act": SpeechAct.UNCLEAR,
        "domain": IntentDomain.UNKNOWN,
        "operation": IntentOperation.CLARIFY,
        "route": IntentRoute.AMBIGUOUS,
        "confidence": 0.4,
        "risk": IntentRisk.MEDIUM,
        "reasons": ["low_confidence_rule"],
        "evidence": ["继续"],
        "needs_clarification": True,
    }
    payload.update(overrides)
    return IntentDecision(**payload)


def test_fallback_decision_trace_contract() -> None:
    decision = FallbackDecision(
        layer=FallbackLayer.RAG,
        reason="rag_empty",
        action=FallbackAction.REPORT_NO_SOURCE,
        user_visible=True,
        recovered=True,
        original_route="knowledge_query",
        final_route="knowledge_query",
    )

    assert decision.to_trace_dict() == {
        "fallback.triggered": True,
        "fallback.layer": "rag",
        "fallback.reason": "rag_empty",
        "fallback.action": "report_no_source",
        "fallback.user_visible": True,
        "fallback.recovered": True,
        "fallback.original_route": "knowledge_query",
        "fallback.final_route": "knowledge_query",
    }


def test_intent_low_confidence_asks_clarification() -> None:
    fallback = intent_fallback_decision(_decision(), original_route="ambiguous")

    assert fallback is not None
    assert fallback.layer == FallbackLayer.INTENT
    assert fallback.reason == "low_confidence"
    assert fallback.action == FallbackAction.ASK_CLARIFICATION
    assert fallback.user_visible is True


def test_intent_conflict_disables_fast_path() -> None:
    fallback = intent_fallback_decision(
        _decision(route=IntentRoute.MEMORY_QUERY),
        conflict_reason="legacy_fact_update_intent_memory_query",
        original_route="fact_update",
    )

    assert fallback is not None
    assert fallback.action == FallbackAction.DISABLE_FAST_PATH
    assert fallback.recovered is True
    assert fallback.original_route == "fact_update"
    assert fallback.final_route == "memory_query"


def test_memory_missing_uses_honest_reply_fallback() -> None:
    result = answer_memory_query("我是谁", mem0_memories=[])

    fallback = memory_query_fallback_decision(result)

    assert fallback is not None
    assert fallback.layer == FallbackLayer.MEMORY
    assert fallback.action == FallbackAction.HONEST_MISSING_MEMORY
    assert fallback.user_visible is True


def test_rag_empty_and_weak_hit_fallbacks() -> None:
    first_pass = rag_quality_fallback_decision(
        rag_skipped=False,
        chunks=[],
        threshold=0.3,
    )
    weak_final = rag_quality_fallback_decision(
        rag_skipped=False,
        chunks=[RagChunk(doc_id="d1", chunk_id="c1", text="weak", score=0.1)],
        threshold=0.3,
        second_pass=True,
        final=True,
    )

    assert first_pass is not None
    assert first_pass.reason == "rag_empty"
    assert first_pass.action == FallbackAction.SECOND_PASS_RETRIEVAL
    assert first_pass.user_visible is False
    assert weak_final is not None
    assert weak_final.reason == "rag_weak_hit"
    assert weak_final.action == FallbackAction.REPORT_NO_SOURCE
    assert weak_final.user_visible is True


def test_tool_llm_schema_and_output_guard_fallbacks() -> None:
    assert tool_fallback_decision("tool_not_allowed").action == FallbackAction.TOOL_UNAVAILABLE_REPLY
    assert llm_fallback_decision("timeout").action == FallbackAction.RETRY_ONCE
    assert schema_fallback_decision("schema_invalid").action == FallbackAction.REPAIR_ONCE
    assert (
        output_guard_fallback_decision("policy_violation").action
        == FallbackAction.RETRACT_REPLACE_REFUSAL
    )


def test_fallback_metadata_maps_through_path_metrics_and_events() -> None:
    fallback = output_guard_fallback_decision("policy_violation")
    metrics = record_fallback_decision(None, fallback)
    meta = path_metrics_metadata(metrics)

    assert meta["fallback_count"] == 1
    assert meta["fallback.triggered"] is True
    assert meta["fallback.layer"] == "output_guard"
    assert meta["fallback.reason"] == "policy_violation"

    event_meta = event_to_metadata(
        ObservabilityEvent(
            ObservabilityEventType.FALLBACK_TRIGGERED,
            fallback.to_trace_dict(),
        )
    )
    assert event_meta["fallback.action"] == "retract_replace_refusal"
