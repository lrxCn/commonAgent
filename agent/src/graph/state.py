"""LangGraph AgentState for the Supervisor main graph."""

from __future__ import annotations

from typing import Annotated

from langchain_core.messages import BaseMessage
from langgraph.channels.ephemeral_value import EphemeralValue
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict

from contracts.context import ContextBundle
from contracts.intent import IntentDecision
from contracts.memory_write import StructuredMemoryRecord
from gateway.schemas import ClientAction
from rag.retriever import RagChunk


class AgentState(TypedDict, total=False):
    """Main graph state.

    Per-turn pipeline fields use ``EphemeralValue`` so they are not read from
    checkpoint on the next ``invoke``. Request identity and tools live in
    ``context_schema`` (see ``graph.context.GraphContextSchema``).
    """

    messages: Annotated[list[BaseMessage], add_messages]
    user_memories: Annotated[list[str], EphemeralValue]
    rolling_summary: Annotated[str | None, EphemeralValue]
    # ``turn_type`` / ``turn_type_reason`` are derived from ``intent_decision`` in load_memory.
    turn_type: Annotated[str, EphemeralValue]
    turn_type_reason: Annotated[str, EphemeralValue]
    intent_decision: Annotated[IntentDecision, EphemeralValue]
    # Kept for compatibility; false when IntentDecision is the sole authority (task 60+).
    intent_conflict: Annotated[bool, EphemeralValue]
    intent_conflict_reason: Annotated[str, EphemeralValue]
    intent_shadow_error: Annotated[str, EphemeralValue]
    policy_fast_path_allowed: Annotated[bool, EphemeralValue]
    policy_denied_reason: Annotated[str, EphemeralValue]
    memory_write_record: Annotated[StructuredMemoryRecord | None, EphemeralValue]
    path_metrics: Annotated[dict[str, object], EphemeralValue]
    rewritten_query: Annotated[str, EphemeralValue]
    rag_skipped: Annotated[bool, EphemeralValue]
    rag_chunks: Annotated[list[RagChunk], EphemeralValue]
    context_bundle: Annotated[ContextBundle, EphemeralValue]
    # Compatibility fields derived from ``context_bundle`` for existing traces/tests.
    system_prompt: Annotated[str, EphemeralValue]
    context_budget: Annotated[dict[str, object], EphemeralValue]
    executor: Annotated[str, EphemeralValue]
    executor_reason: Annotated[str, EphemeralValue]
    inbound_blocked: Annotated[bool, EphemeralValue]
    inbound_block_message: Annotated[str, EphemeralValue]
    supervisor_draft: Annotated[str, EphemeralValue]
    outbound_blocked: Annotated[bool, EphemeralValue]
    client_actions: Annotated[list[ClientAction] | None, EphemeralValue]
    client_actions_error: Annotated[dict[str, str] | None, EphemeralValue]
