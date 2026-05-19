"""Smoke tests for main graph compilation and supervisor defaults."""

from langgraph.checkpoint.memory import MemorySaver
from langgraph.pregel import Pregel

from graph.build import compile_graph
from graph.supervisor import DEFAULT_SUPERVISOR_INSTRUCTIONS


def test_graph_compiles() -> None:
    graph = compile_graph(checkpointer=MemorySaver(), use_pooled_postgres=False)
    assert isinstance(graph, Pregel)


def test_supervisor_instructions_is_nonempty() -> None:
    assert len(DEFAULT_SUPERVISOR_INSTRUCTIONS.strip()) > 0
