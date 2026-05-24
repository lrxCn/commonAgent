"""Route functions that connect graph stages."""

from __future__ import annotations

from typing import Literal

from graph.state import AgentState


def route_after_load_memory(
    state: AgentState,
) -> Literal["fact_update_confirm", "memory_query_reply", "chitchat_reply", "rewrite"]:
    """Route fact updates/chitchat to lightweight executors after turn classification."""
    if state.get("policy_fast_path_allowed") is True:
        return "fact_update_confirm"
    intent_decision = state.get("intent_decision")
    if (
        intent_decision is not None
        and getattr(intent_decision, "route", "") == "memory_query"
    ) or state.get("turn_type") == "memory_query":
        return "memory_query_reply"
    if state.get("turn_type") == "chitchat":
        return "chitchat_reply"
    return "rewrite"


def route_after_supervisor(
    state: AgentState,
) -> Literal["client_actions_emit", "outbound_guard"]:
    """Skip outbound text guard when structured client_actions are ready."""
    if state.get("client_actions"):
        return "client_actions_emit"
    return "outbound_guard"
