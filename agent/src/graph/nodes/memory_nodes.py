"""Memory and checkpoint-history graph adapters."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import cast

from langchain_core.messages import BaseMessage, HumanMessage
from langgraph.runtime import Runtime
from langgraph.types import RunnableConfig

from contracts.events import ObservabilityEventType
from contracts.intent import IntentDecision
from contracts.routing import TurnType, TurnTypeDecision
from graph.context import GraphContextSchema, request_context_from_runtime
from graph.state import AgentState
from intent.engine import classify_intent, turn_type_decision_from_intent
from intent.fallback import intent_fallback_decision, policy_denied_fallback_decision
from intent.policy import decide_fast_path_policy
from intent.signals import extract_signals
from memory.history import get_rolling_summary, load_thread_messages
from memory.mem0_client import fetch_user_memories
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

    with ThreadPoolExecutor(max_workers=3) as pool:
        mem0_future = pool.submit(fetch_memories, ctx.user_id)
        history_future = pool.submit(load_messages, thread_id)
        summary_future = pool.submit(load_summary, thread_id)
        mem0_memories = mem0_future.result()
        checkpoint_messages = history_future.result()
        rolling_summary = summary_future.result()

    updates: dict[str, object] = {
        "mem0_memories": mem0_memories,
        "rolling_summary": rolling_summary,
    }

    incoming = list(state.get("messages") or [])
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
        policy_decision = decide_fast_path_policy(
            intent_decision,
            signals=extract_signals(user_message, tools_context=ctx.tools),
        )
        updates["policy_fast_path_allowed"] = policy_decision.fast_path_allowed
        updates["policy_denied_reason"] = policy_decision.denied_reason
        fallback_decision = intent_fallback_decision(
            intent_decision,
            original_route=decision.turn_type.value,
        )
        if fallback_decision is None and decision.turn_type.value == "fact_update":
            fallback_decision = policy_denied_fallback_decision(
                policy_decision.denied_reason,
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
            policy_decision.to_trace_dict(),
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
