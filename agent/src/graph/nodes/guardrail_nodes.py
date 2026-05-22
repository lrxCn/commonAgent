"""Inbound and outbound guardrail graph adapters."""

from __future__ import annotations

from typing import Literal

from langchain_core.messages import AIMessage

from graph.state import AgentState
from guardrails.inbound import check_inbound
from guardrails.outbound import OUTBOUND_SAFE_REPLY, check_outbound
from settings.config import get_settings

from .common import extract_user_message, merge_carry, text


def inbound_guard_node(state: AgentState) -> dict[str, object]:
    """Run inbound guardrails on the current user message."""
    guard = check_inbound(extract_user_message(state), settings=get_settings())
    if guard.allowed:
        return merge_carry(state, {"inbound_blocked": False})

    block_message = guard.message or "Message blocked by inbound guardrails."
    return merge_carry(
        state,
        {
            "inbound_blocked": True,
            "inbound_block_message": block_message,
            "messages": [AIMessage(content=block_message)],
        },
    )


def route_after_inbound(state: AgentState) -> Literal["load_memory", "__end__"]:
    if state.get("inbound_blocked"):
        return "__end__"
    return "load_memory"


def outbound_guard_node(state: AgentState) -> dict[str, object]:
    """Check full supervisor reply before persisting assistant message to checkpoint."""
    draft = text(state.get("supervisor_draft")) or "（无回复）"
    guard = check_outbound(draft, settings=get_settings())

    if guard.allowed:
        return merge_carry(
            state,
            {
                "messages": [AIMessage(content=draft)],
                "outbound_blocked": False,
            },
        )

    safe_reply = guard.message or OUTBOUND_SAFE_REPLY
    return merge_carry(
        state,
        {
            "messages": [AIMessage(content=safe_reply)],
            "outbound_blocked": True,
        },
    )
