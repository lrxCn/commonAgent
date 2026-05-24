"""Post-turn job graph adapter."""

from __future__ import annotations

from langgraph.runtime import Runtime
from langgraph.types import RunnableConfig

from contracts.events import ObservabilityEventType
from graph.context import GraphContextSchema, request_context_from_runtime
from graph.state import AgentState
from memory.post_turn import extract_current_turn_messages, schedule_post_turn_jobs
from observability.path_contract import (
    finalize_path_metrics,
    mark_post_turn_schedule,
)
from observability.tracing import emit_event

from .common import facade_attr, merge_carry, thread_id_from_config


def post_turn_jobs_node(
    state: AgentState,
    runtime: Runtime[GraphContextSchema],
    config: RunnableConfig,
) -> dict[str, object]:
    """Fire-and-forget rolling summary + mem0 write (does not block invoke)."""
    if state.get("inbound_blocked"):
        return merge_carry(state, {})

    finalized_metrics = finalize_path_metrics(state.get("path_metrics"))
    if _skip_mem0_for_denied_fact_update(state):
        metrics = mark_post_turn_schedule(finalized_metrics, scheduled=False)
        emit_event(
            ObservabilityEventType.POST_TURN_SCHEDULED,
            {
                "path_metrics": metrics,
                "post_turn.skip_reason": "policy_denied_fact_update",
            },
        )
        return merge_carry(state, {"path_metrics": metrics})
    if _skip_mem0_for_memory_query(state):
        metrics = mark_post_turn_schedule(finalized_metrics, scheduled=False)
        emit_event(
            ObservabilityEventType.POST_TURN_SCHEDULED,
            {
                "path_metrics": metrics,
                "post_turn.skip_reason": "memory_query",
            },
        )
        return merge_carry(state, {"path_metrics": metrics})

    ctx = request_context_from_runtime(runtime)
    thread_id = thread_id_from_config(config)
    extract_messages = facade_attr(
        "extract_current_turn_messages",
        extract_current_turn_messages,
    )
    turn_messages = extract_messages(state.get("messages") or [])
    if not turn_messages:
        metrics = mark_post_turn_schedule(finalized_metrics, scheduled=False)
        emit_event(
            ObservabilityEventType.POST_TURN_SCHEDULED,
            {"path_metrics": metrics},
        )
        return merge_carry(state, {"path_metrics": metrics})

    try:
        facade_attr("schedule_post_turn_jobs", schedule_post_turn_jobs)(
            thread_id=thread_id,
            user_id=ctx.user_id,
            turn_messages=turn_messages,
        )
    except Exception as exc:
        metrics = mark_post_turn_schedule(
            finalized_metrics,
            scheduled=False,
            error=type(exc).__name__,
        )
        emit_event(
            ObservabilityEventType.POST_TURN_SCHEDULED,
            {"path_metrics": metrics},
        )
        return merge_carry(state, {"path_metrics": metrics})

    metrics = mark_post_turn_schedule(finalized_metrics, scheduled=True)
    emit_event(
        ObservabilityEventType.POST_TURN_SCHEDULED,
        {"path_metrics": metrics},
    )
    return merge_carry(state, {"path_metrics": metrics})


def _skip_mem0_for_denied_fact_update(state: AgentState) -> bool:
    return (
        state.get("turn_type") == "fact_update"
        and state.get("policy_fast_path_allowed") is not True
    )


def _skip_mem0_for_memory_query(state: AgentState) -> bool:
    intent_decision = state.get("intent_decision")
    return (
        state.get("turn_type") == "memory_query"
        or state.get("executor") == "memory_query_executor"
        or (
            intent_decision is not None
            and getattr(intent_decision, "route", "") == "memory_query"
        )
    )
