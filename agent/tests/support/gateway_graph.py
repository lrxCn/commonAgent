"""Install mocked Supervisor graph for Gateway HTTP tests."""

from __future__ import annotations

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.memory import MemorySaver

from gateway.chat import reset_chat_graph, set_chat_graph
from graph.build import compile_graph
from graph.supervisor import reset_supervisor_overrides, set_answer_invoke, set_supervisor_invoke
from settings.config import Settings, reset_settings, set_settings_override

_GATEWAY_GRAPH_ENV: dict[str, object] = {
    "LANGSMITH_API_KEY": "lsv2_test",
    "OPENAI_API_KEY": "sk-test",
    "DATABASE_URL": "postgresql://postgres:test@localhost:5432/common_agent",
    "GUARDRAILS_ENABLED": False,
    "MEM0_MOCK": True,
    "QDRANT_MOCK": True,
    "RAG_ROUTER_MODE": "rules",
}


def install_gateway_graph_mocks(
    monkeypatch: pytest.MonkeyPatch,
    *,
    settings: Settings | None = None,
    supervisor_reply: str | None = None,
) -> None:
    """Patch graph nodes and wire MemorySaver graph into Gateway."""
    monkeypatch.setattr("graph.nodes.load_thread_messages", lambda _thread_id: [])
    monkeypatch.setattr("graph.nodes.get_rolling_summary", lambda _thread_id: None)
    monkeypatch.setattr("graph.nodes.schedule_post_turn_jobs", lambda **_kwargs: None)

    reset_settings()
    reset_supervisor_overrides()
    reset_chat_graph()

    set_settings_override(settings or Settings(**_GATEWAY_GRAPH_ENV))  # type: ignore[arg-type]

    def _fake_supervisor(_system: str, messages: list) -> list:
        last_human = ""
        for message in reversed(messages):
            if isinstance(message, HumanMessage):
                last_human = str(message.content)
                break
        content = supervisor_reply if supervisor_reply is not None else f"mock-reply:{last_human}"
        return [AIMessage(content=content)]

    set_supervisor_invoke(_fake_supervisor)
    set_answer_invoke(lambda system, messages: str(_fake_supervisor(system, messages)[0].content))
    set_chat_graph(compile_graph(checkpointer=MemorySaver(), use_pooled_postgres=False))


def teardown_gateway_graph_mocks() -> None:
    reset_supervisor_overrides()
    reset_chat_graph()
    reset_settings()
