"""Context assembly graph adapter."""

from __future__ import annotations

from langgraph.runtime import Runtime

from graph.context import GraphContextSchema, request_context_from_runtime
from graph.state import AgentState
from graph.supervisor import DEFAULT_SUPERVISOR_INSTRUCTIONS, build_supervisor_instructions
from memory.assembly import build_context_bundle

from .common import extract_user_message, merge_carry


def context_assembly_node(
    state: AgentState,
    runtime: Runtime[GraphContextSchema],
) -> dict[str, object]:
    """Assemble the single model context bundle (K+M+summary+mem0+RAG)."""
    ctx = request_context_from_runtime(runtime)
    instructions = build_supervisor_instructions(
        DEFAULT_SUPERVISOR_INSTRUCTIONS,
        ctx.tools,
    )
    bundle = build_context_bundle(
        user_memories=list(state.get("user_memories") or []),
        summary=state.get("rolling_summary"),
        rag_chunks=state.get("rag_chunks") or [],
        instructions=instructions,
        messages=state.get("messages") or [],
        current_human=extract_user_message(state) or None,
    )
    return merge_carry(
        state,
        {
            "context_bundle": bundle,
            "system_prompt": bundle.system_prompt,
            "context_budget": bundle.budget_metadata(),
        },
    )
