"""Facade for Supervisor graph node adapters.

The public ``graph.nodes`` import path is kept stable while node implementations
live in small stage-oriented modules.
"""

from __future__ import annotations

from guardrails.outbound import OUTBOUND_SAFE_REPLY, check_outbound
from memory.history import get_rolling_summary, load_thread_messages
from memory.read import fetch_user_memories
from memory.post_turn import extract_current_turn_messages, schedule_post_turn_jobs
from rag.retriever import RagChunk, rag_retrieval_node
from rag.rewrite import rewrite_node, should_rewrite
from rag.router import RuleDecision, classify_with_rules, rag_router_node
from settings.config import get_settings

from graph.rag_subagent import (
    apply_rag_subagent_merge,
    run_rag_subagent_retrieval,
    should_delegate_rag_subagent,
)

from .common import (
    _EPHEMERAL_CARRY_KEYS,
    ephemeral_carry as _ephemeral_carry,
    extract_user_message as _extract_user_message,
    extract_user_message_from_messages as _extract_user_message_from_messages,
    merge_carry as _merge_carry,
    text as _text,
    thread_id_from_config as _thread_id,
)
from .context_nodes import context_assembly_node
from .executor_nodes import (
    FACT_UPDATE_CONFIRMATION,
    chitchat_reply_node,
    client_actions_emit_node,
    fact_update_confirm_node,
    memory_query_reply_node,
    supervisor_node,
)
from .guardrail_nodes import inbound_guard_node, outbound_guard_node, route_after_inbound
from .memory_nodes import load_memory_node
from .rag_nodes import (
    rag_retrieval_graph_node,
    rag_router_graph_node,
    rag_subagent_graph_node,
    rewrite_graph_node,
    route_after_rag_retrieval,
)
from .routing_nodes import route_after_load_memory, route_after_supervisor
from .post_turn_nodes import post_turn_jobs_node

__all__ = [
    "FACT_UPDATE_CONFIRMATION",
    "OUTBOUND_SAFE_REPLY",
    "RagChunk",
    "RuleDecision",
    "_EPHEMERAL_CARRY_KEYS",
    "_ephemeral_carry",
    "_extract_user_message",
    "_extract_user_message_from_messages",
    "_merge_carry",
    "_text",
    "_thread_id",
    "apply_rag_subagent_merge",
    "check_outbound",
    "chitchat_reply_node",
    "classify_with_rules",
    "client_actions_emit_node",
    "context_assembly_node",
    "fact_update_confirm_node",
    "extract_current_turn_messages",
    "fetch_user_memories",
    "get_rolling_summary",
    "get_settings",
    "inbound_guard_node",
    "load_memory_node",
    "load_thread_messages",
    "memory_query_reply_node",
    "outbound_guard_node",
    "post_turn_jobs_node",
    "rag_retrieval_graph_node",
    "rag_retrieval_node",
    "rag_router_graph_node",
    "rag_router_node",
    "rag_subagent_graph_node",
    "rewrite_graph_node",
    "rewrite_node",
    "route_after_inbound",
    "route_after_load_memory",
    "route_after_rag_retrieval",
    "route_after_supervisor",
    "run_rag_subagent_retrieval",
    "schedule_post_turn_jobs",
    "should_delegate_rag_subagent",
    "should_rewrite",
    "supervisor_node",
]
