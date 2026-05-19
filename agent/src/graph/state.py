"""LangGraph AgentState for the Supervisor main graph."""

from __future__ import annotations

from typing import Annotated, Any, NotRequired, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

from rag.retriever import RagChunk


class AgentState(TypedDict, total=False):
    """Main graph state.

    ``context`` is supplied on every invoke from the gateway and must not be
    treated as the authority for permissions when resuming from an old checkpoint.
    """

    messages: Annotated[list[BaseMessage], add_messages]
    user_message: str
    context: dict[str, Any]
    mem0_memories: list[str]
    mem0_text: str
    rolling_summary: str | None
    rewritten_query: str
    rag_skipped: bool
    rag_chunks: list[RagChunk]
    system_prompt: str
    inbound_blocked: bool
    inbound_block_message: str
