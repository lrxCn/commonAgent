"""Compile-time tests for the Supervisor main graph."""

from __future__ import annotations

import pytest
from langgraph.checkpoint.memory import MemorySaver

from graph.build import compile_graph, get_graph, reset_compiled_graph
from settings.config import Settings, reset_settings, set_settings_override

_REQUIRED_ENV = {
    "LANGSMITH_API_KEY": "lsv2_test",
    "OPENAI_API_KEY": "sk-test",
    "DATABASE_URL": "postgresql://postgres:test@localhost:5432/common_agent",
}


@pytest.fixture(autouse=True)
def _settings_and_graph_cache() -> None:
    reset_compiled_graph()
    reset_settings()
    set_settings_override(Settings(**_REQUIRED_ENV))  # type: ignore[arg-type]
    yield
    reset_compiled_graph()
    reset_settings()


def test_compile_graph_has_expected_nodes() -> None:
    graph = compile_graph(checkpointer=MemorySaver(), use_pooled_postgres=False)
    node_names = set(graph.nodes.keys())
    expected = {
        "__start__",
        "inbound_guard",
        "load_memory",
        "rewrite",
        "rag_router",
        "rag_retrieval",
        "context_assembly",
        "supervisor",
    }
    assert expected.issubset(node_names)


def test_get_graph_returns_compiled_instance() -> None:
    graph = compile_graph(checkpointer=MemorySaver(), use_pooled_postgres=False)
    reset_compiled_graph()

    import graph.build as build_mod

    build_mod._compiled_graph = graph
    assert get_graph() is graph


def test_compile_graph_registers_context_schema() -> None:
    from graph.context import GraphContextSchema

    graph = compile_graph(checkpointer=MemorySaver(), use_pooled_postgres=False)
    assert graph.context_schema is GraphContextSchema
