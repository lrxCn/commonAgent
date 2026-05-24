"""Route functions that connect graph stages."""

from __future__ import annotations

from typing import Literal

from graph.state import AgentState


def route_after_load_memory(
    state: AgentState,
) -> Literal["fact_update_confirm", "chitchat_reply", "rewrite"]:
    """Route fact updates/chitchat to lightweight executors after turn classification."""
    if state.get("policy_fast_path_allowed") is True:
        return "fact_update_confirm"
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
