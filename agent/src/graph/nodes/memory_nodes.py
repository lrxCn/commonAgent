"""Memory and checkpoint-history graph adapters."""

from __future__ import annotations

from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from typing import Any, cast

from langchain_core.messages import BaseMessage, HumanMessage
from langgraph.runtime import Runtime
from langgraph.types import RunnableConfig

from contracts.events import ObservabilityEventType
from contracts.intent import IntentDecision
from contracts.memory_write import StructuredMemoryRecord
from contracts.routing import TurnType, TurnTypeDecision
from graph.context import GraphContextSchema, request_context_from_runtime
from graph.state import AgentState
from intent.engine import classify_intent, turn_type_decision_from_intent
from intent.fallback import intent_fallback_decision, policy_denied_fallback_decision
from intent.policy import decide_fast_path_policy
from intent.signals import extract_signals
from memory.history import get_rolling_summary, load_thread_messages
from memory.read import fetch_user_memories
from memory.structured_record import build_structured_memory_record
from observability.path_contract import new_path_metrics, record_fallback_decision
from observability.tracing import emit_event

from .common import (
    extract_user_message_from_messages,
    facade_attr,
    merge_carry,
    thread_id_from_config,
)


def load_memory_node(
    state: AgentState,
    runtime: Runtime[GraphContextSchema],
    config: RunnableConfig,
) -> dict[str, object]:
    """Fetch mem0 and checkpoint history in parallel (thread pool)."""
    ctx = request_context_from_runtime(runtime)
    thread_id = thread_id_from_config(config)

    fetch_memories = facade_attr("fetch_user_memories", fetch_user_memories)
    load_messages = facade_attr("load_thread_messages", load_thread_messages)
    load_summary = facade_attr("get_rolling_summary", get_rolling_summary)

    incoming = list(state.get("messages") or [])
    prefetch_messages = incoming
    user_message = extract_user_message_from_messages(prefetch_messages)

    with ThreadPoolExecutor(max_workers=3) as pool:
        mem0_future = pool.submit(
            fetch_memories,
            ctx.user_id,
            query=user_message or None,
        )
        history_future = pool.submit(load_messages, thread_id)
        summary_future = pool.submit(load_summary, thread_id)
        mem0_memories = mem0_future.result()
        checkpoint_messages = history_future.result()
        rolling_summary = summary_future.result()

    updates: dict[str, object] = {
        "mem0_memories": mem0_memories,
        "rolling_summary": rolling_summary,
    }

    if not incoming and checkpoint_messages:
        updates["messages"] = checkpoint_messages
    elif checkpoint_messages and incoming:
        if len(incoming) == 1 and isinstance(incoming[0], HumanMessage):
            updates["messages"] = [*checkpoint_messages, incoming[0]]

    classify_messages = cast(list[BaseMessage], updates.get("messages") or incoming)
    user_message = extract_user_message_from_messages(classify_messages)

    try:
        intent_decision = classify_intent(user_message, tools_context=ctx.tools)
        decision = turn_type_decision_from_intent(intent_decision)
        updates["turn_type"] = decision.turn_type.value
        updates["turn_type_reason"] = decision.reason
        updates["path_metrics"] = new_path_metrics(
            turn_type=decision.turn_type.value,
            turn_type_reason=decision.reason,
        )
        emit_event(
            ObservabilityEventType.TURN_CLASSIFIED,
            {
                "turn_type": decision.turn_type.value,
                "turn_type_reason": decision.reason,
            },
        )

        updates["intent_decision"] = intent_decision
        updates["intent_conflict"] = False
        updates["intent_conflict_reason"] = ""
        signals = extract_signals(user_message, tools_context=ctx.tools)
        policy_decision = decide_fast_path_policy(
            intent_decision,
            signals=signals,
        )
        updates["policy_fast_path_allowed"] = policy_decision.fast_path_allowed
        updates["policy_denied_reason"] = policy_decision.denied_reason
        updates["memory_write_record"] = None

        if policy_decision.fast_path_allowed:
            memory_write_record = build_structured_memory_record(
                signals,
                intent_decision,
                source_turn_id=_source_turn_id(thread_id, classify_messages),
            )
            if memory_write_record is None:
                updates["policy_fast_path_allowed"] = False
                updates["policy_denied_reason"] = "structured_fill_failed"
            else:
                updates["memory_write_record"] = memory_write_record

        fallback_decision = intent_fallback_decision(
            intent_decision,
            original_route=decision.turn_type.value,
        )
        if fallback_decision is None and decision.turn_type.value == "fact_update":
            fallback_decision = policy_denied_fallback_decision(
                str(updates.get("policy_denied_reason") or ""),
                original_route=decision.turn_type.value,
                final_route=intent_decision.turn_type.value,
            )
        if fallback_decision is not None:
            updates["path_metrics"] = record_fallback_decision(
                updates.get("path_metrics"), fallback_decision
            )
            emit_event(
                ObservabilityEventType.FALLBACK_TRIGGERED,
                fallback_decision.to_trace_dict(),
            )
        intent_metadata = _intent_trace_metadata(intent_decision)
        emit_event(ObservabilityEventType.INTENT_CLASSIFIED, intent_metadata)
        emit_event(
            ObservabilityEventType.POLICY_EVALUATED,
            _policy_trace_metadata(
                policy_decision,
                fast_path_allowed=bool(updates.get("policy_fast_path_allowed")),
                denied_reason=str(updates.get("policy_denied_reason") or ""),
                memory_write_record=updates.get("memory_write_record"),
            ),
        )
    except Exception as exc:
        error = f"{exc.__class__.__name__}: {exc}"
        degraded = TurnTypeDecision(TurnType.GENERAL_CHAT, "intent_classify_error")
        updates["turn_type"] = degraded.turn_type.value
        updates["turn_type_reason"] = degraded.reason
        updates["path_metrics"] = new_path_metrics(
            turn_type=degraded.turn_type.value,
            turn_type_reason=degraded.reason,
        )
        emit_event(
            ObservabilityEventType.TURN_CLASSIFIED,
            {
                "turn_type": degraded.turn_type.value,
                "turn_type_reason": degraded.reason,
            },
        )
        updates["intent_shadow_error"] = error
        updates["intent_conflict"] = False
        updates["intent_conflict_reason"] = ""
        updates["policy_fast_path_allowed"] = False
        updates["policy_denied_reason"] = "intent_classify_error"
        updates["memory_write_record"] = None
        fallback_decision = intent_fallback_decision(
            None,
            conflict_reason="intent_classify_error",
            original_route=degraded.turn_type.value,
        )
        updates["path_metrics"] = record_fallback_decision(
            updates.get("path_metrics"), fallback_decision
        )
        emit_event(
            ObservabilityEventType.INTENT_CLASSIFIED,
            {
                "intent.shadow_error": error,
                "intent.conflict": False,
                "intent.conflict_reason": "",
            },
        )
        emit_event(
            ObservabilityEventType.POLICY_EVALUATED,
            {
                "policy.fast_path_allowed": False,
                "policy.denied_reason": "intent_classify_error",
            },
        )
        emit_event(
            ObservabilityEventType.FALLBACK_TRIGGERED,
            fallback_decision.to_trace_dict(),
        )
    return merge_carry(state, updates)


def _source_turn_id(thread_id: str, messages: Sequence[BaseMessage]) -> str:
    human_turns = sum(1 for message in messages if isinstance(message, HumanMessage))
    return f"{thread_id}:turn-{human_turns or 1}"


def _policy_trace_metadata(
    policy_decision: object,
    *,
    fast_path_allowed: bool,
    denied_reason: str,
    memory_write_record: object | None,
) -> dict[str, object]:
    trace = cast(Any, policy_decision).to_trace_dict()
    trace["policy.fast_path_allowed"] = fast_path_allowed
    trace["policy.denied_reason"] = denied_reason
    if memory_write_record is not None:
        record = cast(StructuredMemoryRecord, memory_write_record)
        trace["memory_write.mode"] = "structured"
        trace["memory_write.record.attribute"] = record.attribute
        trace["memory_write.extraction_method"] = record.extraction_method
    elif denied_reason == "structured_fill_failed":
        trace["memory_write.structured_fill_failed"] = True
    return trace


def _intent_trace_metadata(intent_decision: IntentDecision) -> dict[str, object]:
    trace = intent_decision.to_trace_dict()
    return {
        "intent.speech_act": trace.get("speech_act", ""),
        "intent.domain": trace.get("domain", ""),
        "intent.operation": trace.get("operation", ""),
        "intent.route": trace.get("route", ""),
        "intent.confidence": trace.get("confidence", 0.0),
        "intent.risk": trace.get("risk", ""),
        "intent.reasons": trace.get("reasons", []),
        "intent.needs_clarification": trace.get("needs_clarification", False),
        "intent.conflict": False,
        "intent.conflict_reason": "",
    }
