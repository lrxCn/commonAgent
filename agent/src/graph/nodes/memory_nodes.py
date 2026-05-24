"""Memory and checkpoint-history graph adapters."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import cast

from langchain_core.messages import BaseMessage, HumanMessage
from langgraph.runtime import Runtime
from langgraph.types import RunnableConfig

from contracts.events import ObservabilityEventType
from contracts.intent import IntentDecision
from graph.context import GraphContextSchema, request_context_from_runtime
from graph.state import AgentState
from graph.turn_type import classify_turn_type
from intent.engine import classify_intent
from intent.policy import decide_fast_path_policy
from intent.signals import extract_signals
from memory.history import get_rolling_summary, load_thread_messages
from memory.mem0_client import fetch_user_memories
from observability.path_contract import new_path_metrics
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
    decision = classify_turn_type(
        extract_user_message_from_messages(classify_messages),
        tools_context=ctx.tools,
    )
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
        }
    )

    user_message = extract_user_message_from_messages(classify_messages)
    try:
        intent_decision = classify_intent(user_message, tools_context=ctx.tools)
        conflict = intent_decision.turn_type.value != decision.turn_type.value
        conflict_reason = (
            f"legacy_{decision.turn_type.value}_intent_{intent_decision.route}"
            if conflict
            else ""
        )
        updates["intent_decision"] = intent_decision
        updates["intent_conflict"] = conflict
        updates["intent_conflict_reason"] = conflict_reason
        policy_decision = decide_fast_path_policy(
            intent_decision,
            signals=extract_signals(user_message, tools_context=ctx.tools),
        )
        updates["policy_fast_path_allowed"] = policy_decision.fast_path_allowed
        updates["policy_denied_reason"] = policy_decision.denied_reason
        intent_metadata = _intent_shadow_metadata(
            intent_decision,
            legacy_turn_type=decision.turn_type.value,
            legacy_turn_type_reason=decision.reason,
            conflict=conflict,
            conflict_reason=conflict_reason,
        )
        emit_event(ObservabilityEventType.INTENT_CLASSIFIED, intent_metadata)
        if conflict:
            emit_event(ObservabilityEventType.INTENT_CONFLICT_DETECTED, intent_metadata)
        emit_event(
            ObservabilityEventType.POLICY_EVALUATED,
            policy_decision.to_trace_dict(),
        )
    except Exception as exc:
        error = f"{exc.__class__.__name__}: {exc}"
        updates["intent_shadow_error"] = error
        updates["policy_fast_path_allowed"] = False
        updates["policy_denied_reason"] = "intent_shadow_error"
        emit_event(
            ObservabilityEventType.INTENT_CLASSIFIED,
            {
                "intent.shadow_error": error,
                "intent.legacy_turn_type": decision.turn_type.value,
                "intent.legacy_turn_type_reason": decision.reason,
                "intent.conflict": False,
                "intent.conflict_reason": "",
            },
        )
        emit_event(
            ObservabilityEventType.POLICY_EVALUATED,
            {
                "policy.fast_path_allowed": False,
                "policy.denied_reason": "intent_shadow_error",
            },
        )
    return merge_carry(state, updates)


def _intent_shadow_metadata(
    intent_decision: IntentDecision,
    *,
    legacy_turn_type: str,
    legacy_turn_type_reason: str,
    conflict: bool,
    conflict_reason: str,
) -> dict[str, object]:
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
        "intent.legacy_turn_type": legacy_turn_type,
        "intent.legacy_turn_type_reason": legacy_turn_type_reason,
        "intent.conflict": conflict,
        "intent.conflict_reason": conflict_reason,
    }
