"""Post-turn job graph adapter."""

from __future__ import annotations

from langgraph.runtime import Runtime
from langgraph.types import RunnableConfig

from graph.context import GraphContextSchema, request_context_from_runtime
from graph.state import AgentState
from memory.post_turn import extract_current_turn_messages, schedule_post_turn_jobs
from observability.path_contract import (
    finalize_path_metrics,
    mark_post_turn_schedule,
)
from observability.tracing import attach_run_metadata, build_path_contract_trace_metadata

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

    ctx = request_context_from_runtime(runtime)
    thread_id = thread_id_from_config(config)
    extract_messages = facade_attr(
        "extract_current_turn_messages",
        extract_current_turn_messages,
    )
    turn_messages = extract_messages(state.get("messages") or [])
    if not turn_messages:
        metrics = mark_post_turn_schedule(finalized_metrics, scheduled=False)
        attach_run_metadata(build_path_contract_trace_metadata(metrics))
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
        attach_run_metadata(build_path_contract_trace_metadata(metrics))
        return merge_carry(state, {"path_metrics": metrics})

    metrics = mark_post_turn_schedule(finalized_metrics, scheduled=True)
    attach_run_metadata(build_path_contract_trace_metadata(metrics))
    return merge_carry(state, {"path_metrics": metrics})
