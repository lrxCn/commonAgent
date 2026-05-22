"""Intent shadow observability in the graph without path takeover."""

from __future__ import annotations

from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import MemorySaver
import pytest

from contracts.events import ObservabilityEventType
from gateway.schemas import RequestContext
from graph.build import compile_graph
from graph.context import graph_context_from_request
from graph.nodes import load_memory_node
from graph.supervisor import reset_supervisor_overrides, set_answer_invoke
from observability.events import collect_events
from settings.config import Settings, reset_settings, set_settings_override

_REQUIRED_ENV = {
    "LANGSMITH_API_KEY": "lsv2_test",
    "OPENAI_API_KEY": "sk-test",
    "DATABASE_URL": "postgresql://postgres:test@localhost:5432/common_agent",
    "GUARDRAILS_ENABLED": False,
    "MEM0_MOCK": True,
    "QDRANT_MOCK": True,
    "RAG_ROUTER_MODE": "rules",
}


@pytest.fixture(autouse=True)
def _graph_mocks(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("graph.nodes.load_thread_messages", lambda _thread_id: [])
    monkeypatch.setattr("graph.nodes.get_rolling_summary", lambda _thread_id: None)
    monkeypatch.setattr("graph.nodes.schedule_post_turn_jobs", lambda **_kwargs: None)
    reset_supervisor_overrides()
    set_answer_invoke(lambda _system, _messages: "mock answer")
    reset_settings()
    set_settings_override(Settings(**_REQUIRED_ENV))  # type: ignore[arg-type]
    yield
    reset_supervisor_overrides()
    reset_settings()


def _context() -> dict[str, object]:
    return graph_context_from_request(
        RequestContext(user_id="user-1", role_id="role-sales", tools=[])
    )


def test_intent_shadow_records_conflict_without_taking_over_legacy_path() -> None:
    graph = compile_graph(checkpointer=MemorySaver(), use_pooled_postgres=False)
    result = graph.invoke(
        {"messages": [HumanMessage(content="我的名字是什么？")]},
        context=_context(),
        config={"configurable": {"thread_id": "intent-shadow-memory-query"}},
    )

    assert result["turn_type"] == "knowledge_query"
    assert result["turn_type_reason"] == "knowledge_intent_rule"
    assert result["path_metrics"]["path_contract"] == "pass"
    assert result["intent_decision"].route == "memory_query"
    assert result["intent_conflict"] is True
    assert result["intent_conflict_reason"] == "legacy_knowledge_query_intent_memory_query"


def test_load_memory_node_emits_intent_shadow_metadata() -> None:
    runtime = type(
        "RuntimeStub",
        (),
        {"context": {"user_id": "user-1", "role_id": "role-sales", "tools": []}},
    )()
    with collect_events() as events:
        load_memory_node(
            {"messages": [HumanMessage(content="我的名字是什么？")]},
            runtime,  # type: ignore[arg-type]
            {"configurable": {"thread_id": "intent-shadow-node"}},
        )
    intent_events = [
        event
        for event in events
        if event.name == ObservabilityEventType.INTENT_CLASSIFIED.value
    ]
    assert len(intent_events) == 1
    metadata = intent_events[0].metadata
    assert metadata["intent.route"] == "memory_query"
    assert metadata["intent.legacy_turn_type"] == "knowledge_query"
    assert metadata["intent.conflict"] is True


def test_intent_shadow_error_does_not_change_legacy_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _raise(*_args: object, **_kwargs: object) -> object:
        raise RuntimeError("shadow failed")

    monkeypatch.setattr("graph.nodes.memory_nodes.classify_intent", _raise)
    graph = compile_graph(checkpointer=MemorySaver(), use_pooled_postgres=False)

    result = graph.invoke(
        {"messages": [HumanMessage(content="你好")]},
        context=_context(),
        config={"configurable": {"thread_id": "intent-shadow-error"}},
    )

    assert result["turn_type"] == "chitchat"
    assert result["path_metrics"]["fast_path"] is True
    assert result["path_metrics"]["path_contract"] == "pass"
    assert "RuntimeError: shadow failed" in result["intent_shadow_error"]
    assert "intent_decision" not in result

    runtime = type(
        "RuntimeStub",
        (),
        {"context": {"user_id": "user-1", "role_id": "role-sales", "tools": []}},
    )()
    with collect_events() as events:
        load_memory_node(
            {"messages": [HumanMessage(content="你好")]},
            runtime,  # type: ignore[arg-type]
            {"configurable": {"thread_id": "intent-shadow-error-node"}},
        )
    metadata = [
        event.metadata
        for event in events
        if event.name == ObservabilityEventType.INTENT_CLASSIFIED.value
    ][0]
    assert metadata["intent.shadow_error"] == "RuntimeError: shadow failed"
    assert metadata["intent.legacy_turn_type"] == "chitchat"
