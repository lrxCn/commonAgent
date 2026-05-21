"""Graph wiring for fire-and-forget post-turn jobs."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.memory import MemorySaver

from gateway.schemas import RequestContext
from graph.build import compile_graph
from graph.context import graph_context_from_request
from graph.supervisor import reset_supervisor_overrides, set_answer_invoke, set_supervisor_invoke
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
def _graph_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("graph.nodes.load_thread_messages", lambda _thread_id: [])
    monkeypatch.setattr("graph.nodes.get_rolling_summary", lambda _thread_id: None)
    reset_settings()
    set_settings_override(Settings(**_REQUIRED_ENV))  # type: ignore[arg-type]
    reset_supervisor_overrides()
    set_supervisor_invoke(
        lambda _system, messages: [
            AIMessage(content=f"reply:{messages[-1].content}"),
        ]
    )
    set_answer_invoke(lambda _system, messages: f"reply:{messages[-1].content}")
    yield
    reset_supervisor_overrides()
    reset_settings()


def test_invoke_schedules_post_turn_jobs_without_blocking(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    schedule_mock = MagicMock()
    monkeypatch.setattr("graph.nodes.schedule_post_turn_jobs", schedule_mock)

    graph = compile_graph(checkpointer=MemorySaver(), use_pooled_postgres=False)
    ctx = graph_context_from_request(
        RequestContext(user_id="user-pt", role_id="role-1", tools=[]),
    )
    result = graph.invoke(
        {"messages": [HumanMessage(content="hello")]},
        context=ctx,
        config={"configurable": {"thread_id": "thread-pt-1"}},
    )

    assert schedule_mock.call_count == 1
    kwargs = schedule_mock.call_args.kwargs
    assert kwargs["thread_id"] == "thread-pt-1"
    assert kwargs["user_id"] == "user-pt"
    assert len(kwargs["turn_messages"]) == 2
    assert result.get("messages")
