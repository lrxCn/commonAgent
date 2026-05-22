"""Shared helpers for graph node adapters."""

from __future__ import annotations

import sys
from typing import Any

from langchain_core.messages import BaseMessage, HumanMessage
from langgraph.types import RunnableConfig

from graph.state import AgentState

# EphemeralValue channels only expose the previous step's writes; forward keys still
# needed downstream within the same invoke.
_EPHEMERAL_CARRY_KEYS = (
    "mem0_memories",
    "rolling_summary",
    "turn_type",
    "turn_type_reason",
    "path_metrics",
    "rewritten_query",
    "rag_skipped",
    "rag_chunks",
    "context_bundle",
    "system_prompt",
    "context_budget",
    "executor",
    "executor_reason",
    "inbound_blocked",
    "inbound_block_message",
    "supervisor_draft",
    "outbound_blocked",
    "client_actions",
    "client_actions_error",
)


def facade_attr(name: str, default: Any) -> Any:
    """Resolve facade attributes at call time for legacy monkeypatch support."""
    facade = sys.modules.get("graph.nodes")
    if facade is None:
        return default
    return getattr(facade, name, default)


def ephemeral_carry(state: AgentState) -> dict[str, object]:
    carried: dict[str, object] = {}
    for key in _EPHEMERAL_CARRY_KEYS:
        if key not in state:
            continue
        value = state[key]
        if value is None:
            continue
        if isinstance(value, (list, str)) and not value:
            continue
        carried[key] = value
    return carried


def merge_carry(state: AgentState, updates: dict[str, object]) -> dict[str, object]:
    return {**ephemeral_carry(state), **updates}


def text(value: object | None) -> str:
    if value is None:
        return ""
    return str(value).strip()


def thread_id_from_config(config: RunnableConfig | None) -> str:
    configurable = (config or {}).get("configurable") or {}
    thread_id = text(configurable.get("thread_id"))
    if not thread_id:
        raise ValueError("configurable.thread_id is required")
    return thread_id


def extract_user_message(state: AgentState) -> str:
    messages = state.get("messages") or []
    return extract_user_message_from_messages(messages)


def extract_user_message_from_messages(messages: list[BaseMessage]) -> str:
    for message in reversed(messages):
        if isinstance(message, HumanMessage):
            return text(message.content)
    return ""
