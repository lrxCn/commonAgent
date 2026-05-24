"""RAG-related graph adapters."""

from __future__ import annotations

from typing import Any, Literal, cast

from langgraph.runtime import Runtime

from contracts.events import ObservabilityEventType
from graph.context import GraphContextSchema, request_context_from_runtime
from graph.rag_subagent import (
    apply_rag_subagent_merge,
    max_chunk_score,
    run_rag_subagent_retrieval,
    should_delegate_rag_subagent,
)
from graph.state import AgentState
from intent.fallback import llm_fallback_decision, rag_quality_fallback_decision, schema_fallback_decision
from observability.path_contract import record_fallback_decision, update_path_component
from observability.tracing import emit_event
from rag.retriever import rag_retrieval_node
from rag.rewrite import rewrite_node, should_rewrite
from rag.router import RuleDecision, classify_with_rules, rag_router_node
from settings.config import get_settings

from .common import extract_user_message, facade_attr, merge_carry, text


def rewrite_graph_node(state: AgentState) -> dict[str, object]:
    """Delegate to rag.rewrite.rewrite_node with graph state."""
    user_message = extract_user_message(state)
    messages = list(state.get("messages") or [])
    recent_messages = list(messages[:-1]) if messages else []
    settings = get_settings()
    use_skip = settings.REWRITE_SKIP_ENABLED and not settings.REWRITE_FORCE
    should_call, _reason = facade_attr("should_rewrite", should_rewrite)(
        user_message,
        recent_messages=recent_messages,
        mem0_memories=list(state.get("mem0_memories") or []),
        turn_type=_policy_effective_turn_type(state),
        policy_denied_fact_update=_policy_denied_fact_update(state),
    )
    called = bool(user_message) and (should_call or not use_skip)
    payload: dict[str, object] = {
        "user_message": user_message,
        "turn_type": _policy_effective_turn_type(state),
        "policy_fast_path_allowed": state.get("policy_fast_path_allowed") is True,
        "policy_denied_fact_update": _policy_denied_fact_update(state),
        "mem0_memories": state.get("mem0_memories") or [],
        "messages": messages,
    }
    updates = facade_attr("rewrite_node", rewrite_node)(cast(Any, payload))
    path_metrics = update_path_component(
        state.get("path_metrics"),
        "rewrite",
        should_call=should_call,
        called=called,
    )
    path_metrics = _record_upstream_fallback(
        path_metrics,
        updates,
        flag="rewrite.fallback",
        reason_key="rewrite.fallback_reason",
    )
    return merge_carry(state, {**updates, "path_metrics": path_metrics})


def rag_router_graph_node(
    state: AgentState,
    runtime: Runtime[GraphContextSchema],
) -> dict[str, object]:
    """Delegate to rag router with tools from request context."""
    ctx = request_context_from_runtime(runtime)
    message = extract_user_message(state)
    rewritten = state.get("rewritten_query")
    settings = get_settings()
    effective_turn_type = _policy_effective_turn_type(state)
    rule_decision = facade_attr("classify_with_rules", classify_with_rules)(
        message,
        rewritten,
        ctx.tools,
        turn_type=effective_turn_type,
        policy_denied_fact_update=_policy_denied_fact_update(state),
    )
    should_call = (
        rule_decision is RuleDecision.UNCERTAIN
        and settings.RAG_ROUTER_MODE == "hybrid"
    )
    payload: dict[str, object] = {
        "user_message": message,
        "turn_type": effective_turn_type,
        "policy_denied_fact_update": _policy_denied_fact_update(state),
        "rewritten_query": rewritten,
        "tools_context": ctx.tools,
    }
    updates = facade_attr("rag_router_node", rag_router_node)(cast(Any, payload))
    path_metrics = update_path_component(
        state.get("path_metrics"),
        "rag_router",
        should_call=should_call,
        called=should_call,
    )
    path_metrics = _record_upstream_fallback(
        path_metrics,
        updates,
        flag="rag_router.fallback",
        reason_key="rag_router.fallback_reason",
    )
    return merge_carry(state, {**updates, "path_metrics": path_metrics})


def _policy_effective_turn_type(state: AgentState) -> str:
    turn_type = text(state.get("turn_type"))
    if turn_type == "fact_update" and state.get("policy_fast_path_allowed") is not True:
        return ""
    return turn_type


def _policy_denied_fact_update(state: AgentState) -> bool:
    return (
        text(state.get("turn_type")) == "fact_update"
        and state.get("policy_fast_path_allowed") is not True
    )


def _record_upstream_fallback(
    path_metrics: dict[str, object],
    updates: dict[str, object],
    *,
    flag: str,
    reason_key: str,
) -> dict[str, object]:
    if updates.get(flag) is not True:
        return path_metrics
    reason = text(updates.get(reason_key)) or "provider_error"
    if reason in {"parse_failed", "schema_invalid"}:
        fallback_decision = schema_fallback_decision(reason, recovered=True)
    else:
        fallback_decision = llm_fallback_decision(reason, recovered=True)
    path_metrics = record_fallback_decision(path_metrics, fallback_decision)
    emit_event(
        ObservabilityEventType.FALLBACK_TRIGGERED,
        fallback_decision.to_trace_dict(),
    )
    return path_metrics


def rag_retrieval_graph_node(
    state: AgentState,
    runtime: Runtime[GraphContextSchema],
) -> dict[str, object]:
    """Delegate to retriever with role_id from request context."""
    ctx = request_context_from_runtime(runtime)
    should_call = not bool(state.get("rag_skipped", False))
    payload: dict[str, object] = {
        "role_id": ctx.role_id,
        "rewritten_query": state.get("rewritten_query"),
        "rag_skipped": state.get("rag_skipped", False),
    }
    updates = facade_attr("rag_retrieval_node", rag_retrieval_node)(cast(Any, payload))
    path_metrics = update_path_component(
        state.get("path_metrics"),
        "rag",
        should_call=should_call,
        called=should_call,
    )
    fallback_decision = rag_quality_fallback_decision(
        rag_skipped=bool(state.get("rag_skipped", False)),
        chunks=updates.get("rag_chunks") or [],
        threshold=get_settings().RAG_SUBAGENT_SCORE_THRESHOLD,
    )
    if fallback_decision is not None:
        path_metrics = record_fallback_decision(path_metrics, fallback_decision)
        emit_event(
            ObservabilityEventType.FALLBACK_TRIGGERED,
            fallback_decision.to_trace_dict(),
        )
    return merge_carry(state, {**updates, "path_metrics": path_metrics})


def route_after_rag_retrieval(
    state: AgentState,
) -> Literal["rag_subagent", "context_assembly"]:
    """Route to RagSubAgent when primary chunks are empty or below score threshold."""
    should_delegate = facade_attr("should_delegate_rag_subagent", should_delegate_rag_subagent)
    if should_delegate(
        rag_skipped=bool(state.get("rag_skipped")),
        rag_chunks=state.get("rag_chunks") or [],
        settings=get_settings(),
    ):
        return "rag_subagent"
    return "context_assembly"


def rag_subagent_graph_node(
    state: AgentState,
    runtime: Runtime[GraphContextSchema],
) -> dict[str, object]:
    """Second-pass retrieval; merge and dedupe into ``rag_chunks`` (no third pass)."""
    ctx = request_context_from_runtime(runtime)
    role_id = ctx.role_id
    query = text(state.get("rewritten_query"))
    primary = list(state.get("rag_chunks") or [])

    if not role_id or not query:
        return merge_carry(state, {"rag_chunks": primary})

    run_retrieval = facade_attr("run_rag_subagent_retrieval", run_rag_subagent_retrieval)
    apply_merge = facade_attr("apply_rag_subagent_merge", apply_rag_subagent_merge)
    secondary = run_retrieval(role_id, query, settings=get_settings())
    merged = apply_merge(primary, secondary, settings=get_settings())
    updates: dict[str, object] = {"rag_chunks": merged}
    settings = get_settings()
    fallback_decision = rag_quality_fallback_decision(
        rag_skipped=bool(state.get("rag_skipped", False)),
        chunks=merged,
        threshold=settings.RAG_SUBAGENT_SCORE_THRESHOLD,
        second_pass=True,
        final=not merged or max_chunk_score(merged) < settings.RAG_SUBAGENT_SCORE_THRESHOLD,
    )
    if fallback_decision is not None:
        path_metrics = record_fallback_decision(state.get("path_metrics"), fallback_decision)
        emit_event(ObservabilityEventType.FALLBACK_TRIGGERED, fallback_decision.to_trace_dict())
        updates["path_metrics"] = path_metrics
    return merge_carry(state, updates)
