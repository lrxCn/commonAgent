"""Compile the Supervisor main LangGraph."""

from __future__ import annotations

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from graph.nodes import (
    context_assembly_node,
    inbound_guard_node,
    load_memory_node,
    rag_retrieval_graph_node,
    rag_router_graph_node,
    rewrite_graph_node,
    route_after_inbound,
    supervisor_node,
)
from graph.state import AgentState
from memory.checkpointer import get_pooled_checkpointer

_compiled_graph = None


def compile_graph(
    checkpointer: BaseCheckpointSaver | None = None,
    *,
    use_pooled_postgres: bool = True,
):
    """Build and compile the main Supervisor graph."""
    builder = StateGraph(AgentState)

    builder.add_node("inbound_guard", inbound_guard_node)
    builder.add_node("load_memory", load_memory_node)
    builder.add_node("rewrite", rewrite_graph_node)
    builder.add_node("rag_router", rag_router_graph_node)
    builder.add_node("rag_retrieval", rag_retrieval_graph_node)
    builder.add_node("context_assembly", context_assembly_node)
    builder.add_node("supervisor", supervisor_node)

    builder.add_edge(START, "inbound_guard")
    builder.add_conditional_edges(
        "inbound_guard",
        route_after_inbound,
        {"load_memory": "load_memory", "__end__": END},
    )
    builder.add_edge("load_memory", "rewrite")
    builder.add_edge("rewrite", "rag_router")
    builder.add_edge("rag_router", "rag_retrieval")
    builder.add_edge("rag_retrieval", "context_assembly")
    builder.add_edge("context_assembly", "supervisor")
    builder.add_edge("supervisor", END)

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
