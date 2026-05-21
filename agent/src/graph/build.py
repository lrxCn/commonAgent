"""Compile the Supervisor main LangGraph."""

from __future__ import annotations

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from graph.nodes import (
    client_actions_emit_node,
    context_assembly_node,
    fact_update_confirm_node,
    inbound_guard_node,
    load_memory_node,
    outbound_guard_node,
    post_turn_jobs_node,
    route_after_load_memory,
    rag_retrieval_graph_node,
    rag_router_graph_node,
    rag_subagent_graph_node,
    rewrite_graph_node,
    route_after_inbound,
    route_after_rag_retrieval,
    route_after_supervisor,
    supervisor_node,
)
from graph.context import GraphContextSchema
from graph.state import AgentState
from memory.checkpointer import get_pooled_checkpointer
from observability.tracing import configure_tracing_from_settings

_compiled_graph = None


def compile_graph(
    checkpointer: BaseCheckpointSaver | None = None,
    *,
    use_pooled_postgres: bool = True,
):
    """Build and compile the main Supervisor graph."""
    configure_tracing_from_settings()
    builder = StateGraph(AgentState, context_schema=GraphContextSchema)

    builder.add_node("inbound_guard", inbound_guard_node)
    builder.add_node("load_memory", load_memory_node)
    builder.add_node("fact_update_confirm", fact_update_confirm_node)
    builder.add_node("rewrite", rewrite_graph_node)
    builder.add_node("rag_router", rag_router_graph_node)
    builder.add_node("rag_retrieval", rag_retrieval_graph_node)
    builder.add_node("rag_subagent", rag_subagent_graph_node)
    builder.add_node("context_assembly", context_assembly_node)
    builder.add_node("supervisor", supervisor_node)
    builder.add_node("client_actions_emit", client_actions_emit_node)
    builder.add_node("outbound_guard", outbound_guard_node)
    builder.add_node("post_turn_jobs", post_turn_jobs_node)

    builder.add_edge(START, "inbound_guard")
    builder.add_conditional_edges(
        "inbound_guard",
        route_after_inbound,
        {"load_memory": "load_memory", "__end__": END},
    )
    builder.add_conditional_edges(
        "load_memory",
        route_after_load_memory,
        {"fact_update_confirm": "fact_update_confirm", "rewrite": "rewrite"},
    )
    builder.add_edge("fact_update_confirm", "post_turn_jobs")
    builder.add_edge("rewrite", "rag_router")
    builder.add_edge("rag_router", "rag_retrieval")
    builder.add_conditional_edges(
        "rag_retrieval",
        route_after_rag_retrieval,
        {"rag_subagent": "rag_subagent", "context_assembly": "context_assembly"},
    )
    builder.add_edge("rag_subagent", "context_assembly")
    builder.add_edge("context_assembly", "supervisor")
    builder.add_conditional_edges(
        "supervisor",
        route_after_supervisor,
        {"client_actions_emit": "client_actions_emit", "outbound_guard": "outbound_guard"},
    )
    builder.add_edge("client_actions_emit", "post_turn_jobs")
    builder.add_edge("outbound_guard", "post_turn_jobs")
    builder.add_edge("post_turn_jobs", END)

    if checkpointer is not None:
        saver = checkpointer
    elif use_pooled_postgres:
        saver = get_pooled_checkpointer(setup=False)
    else:
        saver = MemorySaver()

    return builder.compile(checkpointer=saver)


def get_graph():
    """LangGraph CLI entrypoint (``langgraph dev``)."""
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = compile_graph()
    return _compiled_graph


def reset_compiled_graph() -> None:
    """Clear cached compiled graph (tests)."""
    global _compiled_graph
    _compiled_graph = None
