"""LangGraph AgentState for the Supervisor main graph."""

from __future__ import annotations

from typing import Annotated

from langchain_core.messages import BaseMessage
from langgraph.channels.ephemeral_value import EphemeralValue
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict

from gateway.schemas import ClientAction
from rag.retriever import RagChunk


class AgentState(TypedDict, total=False):
    """Main graph state.

    Per-turn pipeline fields use ``EphemeralValue`` so they are not read from
    checkpoint on the next ``invoke``. Request identity and tools live in
    ``context_schema`` (see ``graph.context.GraphContextSchema``).
    """

    messages: Annotated[list[BaseMessage], add_messages]
    mem0_memories: Annotated[list[str], EphemeralValue]
    rolling_summary: Annotated[str | None, EphemeralValue]
    rewritten_query: Annotated[str, EphemeralValue]
    rag_skipped: Annotated[bool, EphemeralValue]
    rag_chunks: Annotated[list[RagChunk], EphemeralValue]
    system_prompt: Annotated[str, EphemeralValue]
    inbound_blocked: Annotated[bool, EphemeralValue]
    inbound_block_message: Annotated[str, EphemeralValue]
    supervisor_draft: Annotated[str, EphemeralValue]
    outbound_blocked: Annotated[bool, EphemeralValue]
    client_actions: Annotated[list[ClientAction] | None, EphemeralValue]
    client_actions_error: Annotated[dict[str, str] | None, EphemeralValue]
