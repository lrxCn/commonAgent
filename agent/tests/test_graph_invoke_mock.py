"""End-to-end invoke tests for the Supervisor graph (mocked LLM / retriever)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.memory import MemorySaver

from gateway.schemas import RequestContext
from graph.build import compile_graph
from graph.context import graph_context_from_request
from graph.supervisor import reset_supervisor_overrides, set_answer_invoke, set_supervisor_invoke
from memory.history import set_history_checkpointer
import rag.retriever as retriever_mod
from rag.retriever import RagChunk, reset_retriever_overrides
from rag.rewrite import set_rewrite_llm
from rag.router import set_router_classifier
from settings.config import Settings, reset_settings, set_settings_override

_ORIGINAL_RETRIEVE = retriever_mod.retrieve

_REQUIRED_ENV = {
    "LANGSMITH_API_KEY": "lsv2_test",
    "OPENAI_API_KEY": "sk-test",
    "DATABASE_URL": "postgresql://postgres:test@localhost:5432/common_agent",
    "GUARDRAILS_ENABLED": False,
    "MEMORY_STORE_MOCK": True,
    "QDRANT_MOCK": True,
    "RAG_ROUTER_MODE": "rules",
    "MEMORY_QUERY_POLISH_USE_LLM": False,
}


@pytest.fixture(autouse=True)
def _mock_checkpoint_history(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("graph.nodes.load_thread_messages", lambda _thread_id: [])
    monkeypatch.setattr("graph.nodes.get_rolling_summary", lambda _thread_id: None)
    monkeypatch.setattr("graph.nodes.schedule_post_turn_jobs", lambda **_kwargs: None)


@pytest.fixture(autouse=True)
def _clean_graph_mocks() -> None:
    set_rewrite_llm(lambda _prompt: "rewritten query text")
    set_router_classifier(None)
    reset_retriever_overrides()
    reset_supervisor_overrides()
    set_history_checkpointer(None)
    reset_settings()
    set_settings_override(Settings(**_REQUIRED_ENV))  # type: ignore[arg-type]

    def _fake_supervisor(_system: str, messages: list) -> list:
        last_human = ""
        for message in reversed(messages):
            if isinstance(message, HumanMessage):
                last_human = str(message.content)
                break
        return [AIMessage(content=f"mock-reply:{last_human}")]

    set_supervisor_invoke(_fake_supervisor)
    set_answer_invoke(lambda system, messages: str(_fake_supervisor(system, messages)[0].content))
    yield
    set_rewrite_llm(None)
    set_router_classifier(None)
    reset_retriever_overrides()
    retriever_mod.retrieve = _ORIGINAL_RETRIEVE
    reset_supervisor_overrides()
    set_history_checkpointer(None)
    reset_settings()


def _context(
    *,
    user_id: str = "user-1",
    role_id: str = "role-sales",
    tools: list | None = None,
) -> dict[str, object]:
    ctx = RequestContext(
        user_id=user_id,
        role_id=role_id,
        tools=tools or [],
    )
    return graph_context_from_request(ctx)


def test_invoke_appends_ai_message() -> None:
    graph = compile_graph(checkpointer=MemorySaver(), use_pooled_postgres=False)
    config = {"configurable": {"thread_id": "thread-mock-1"}}
    result = graph.invoke(
        {"messages": [HumanMessage(content="你好")]},
        context=_context(),
        config=config,
    )

    messages = result.get("messages") or []
    assert any(isinstance(message, AIMessage) for message in messages)
    ai_texts = [str(message.content) for message in messages if isinstance(message, AIMessage)]
    assert "你好。" in ai_texts
    assert result.get("rewritten_query") is None
    assert result.get("rag_skipped") is None
    assert "context" not in result


def test_invoke_writes_turn_type_state() -> None:
    graph = compile_graph(checkpointer=MemorySaver(), use_pooled_postgres=False)
    result = graph.invoke(
        {"messages": [HumanMessage(content="我生活在哈尔滨")]},
        context=_context(),
        config={"configurable": {"thread_id": "thread-turn-type-1"}},
    )

    assert result.get("turn_type") == "fact_update"
    assert result.get("turn_type_reason") == result["intent_decision"].turn_type_reason
    assert result.get("rewritten_query") is None
    assert result.get("rag_skipped") is None
    assert result.get("path_metrics", {}).get("fast_path") is True


def test_rag_skipped_does_not_call_retriever() -> None:
    retrieve_mock = MagicMock(return_value=[])
    import rag.retriever as retriever_mod

    retriever_mod.retrieve = retrieve_mock

    graph = compile_graph(checkpointer=MemorySaver(), use_pooled_postgres=False)
    graph.invoke(
        {"messages": [HumanMessage(content="你好")]},
        context=_context(),
        config={"configurable": {"thread_id": "thread-mock-2"}},
    )

    assert retrieve_mock.call_count == 0


def test_chitchat_does_not_call_supervisor() -> None:
    supervisor = MagicMock(return_value=[AIMessage(content="mock-reply:你好")])
    set_supervisor_invoke(supervisor)

    graph = compile_graph(checkpointer=MemorySaver(), use_pooled_postgres=False)
    result = graph.invoke(
        {"messages": [HumanMessage(content="你好")]},
        context=_context(),
        config={"configurable": {"thread_id": "thread-mock-chitchat"}},
    )

    assert supervisor.call_count == 0
    assert result.get("path_metrics", {}).get("fast_path") is True


def test_memory_query_invoke_uses_memory_executor(monkeypatch: pytest.MonkeyPatch) -> None:
    supervisor = MagicMock(return_value=[AIMessage(content="mock-reply:我是谁")])
    monkeypatch.setattr("graph.nodes.fetch_user_memories", lambda _user_id, **_kwargs: ["用户叫刘日兴"])
    set_supervisor_invoke(supervisor)

    graph = compile_graph(checkpointer=MemorySaver(), use_pooled_postgres=False)
    result = graph.invoke(
        {"messages": [HumanMessage(content="我是谁")]},
        context=_context(),
        config={"configurable": {"thread_id": "thread-memory-query-invoke"}},
    )

    assert result["intent_decision"].route == "memory_query"
    assert result["executor"] == "memory_query_executor"
    assert "刘日兴" in str(result["messages"][-1].content)
    assert supervisor.call_count == 0


def test_rag_retrieval_runs_when_router_requests() -> None:
    set_router_classifier(lambda _prompt: '{"need_rag": true}')

    retrieve_mock = MagicMock(
        return_value=[
            RagChunk(
                doc_id="doc-1",
                chunk_id="c-1",
                text="policy text",
                score=0.9,
            )
        ]
    )
    import rag.retriever as retriever_mod

    retriever_mod.retrieve = retrieve_mock

    graph = compile_graph(checkpointer=MemorySaver(), use_pooled_postgres=False)
    result = graph.invoke(
        {"messages": [HumanMessage(content="报销制度是什么？")]},
        context=_context(),
        config={"configurable": {"thread_id": "thread-mock-3"}},
    )

    assert retrieve_mock.call_count == 1
    assert result.get("rag_skipped") is False
    chunks = result.get("rag_chunks") or []
    assert len(chunks) == 1


def test_supervisor_receives_context_bundle_messages() -> None:
    set_router_classifier(lambda _prompt: '{"need_rag": true}')
    import rag.retriever as retriever_mod

    retriever_mod.retrieve = MagicMock(
        return_value=[
            RagChunk(
                doc_id="doc-bundle",
                chunk_id="c-1",
                text="bundle policy text",
                score=0.95,
            )
        ]
    )
    seen: dict[str, object] = {}

    def _capture_answer(system: str, messages: list) -> str:
        seen["system"] = system
        seen["messages"] = list(messages)
        return "bundle answer"

    set_answer_invoke(_capture_answer)

    graph = compile_graph(checkpointer=MemorySaver(), use_pooled_postgres=False)
    result = graph.invoke(
        {"messages": [HumanMessage(content="报销制度是什么？")]},
        context=_context(),
        config={"configurable": {"thread_id": "thread-context-bundle"}},
    )

    bundle = result.get("context_bundle")
    assert bundle is not None
    assert seen["system"] == bundle.system_prompt
    assert seen["messages"] == bundle.messages
    assert result.get("system_prompt") == bundle.system_prompt
    assert result.get("context_budget") == bundle.budget_metadata()
    assert "bundle policy text" in bundle.system_prompt


def test_ephemeral_fields_not_visible_at_start_of_second_invoke(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Second invoke must not read prior turn's rewritten_query from checkpoint."""
    from graph.nodes import rewrite_graph_node as _orig_rewrite

    seen: list[str | None] = []

    def _capture_rewrite(state):  # type: ignore[no-untyped-def]
        seen.append(state.get("rewritten_query"))
        return _orig_rewrite(state)

    monkeypatch.setattr("graph.build.rewrite_graph_node", _capture_rewrite)

    # Compile after patch so the graph binds the wrapped rewrite node.
    graph = compile_graph(checkpointer=MemorySaver(), use_pooled_postgres=False)
    config = {"configurable": {"thread_id": "thread-ephemeral-1"}}
    graph.invoke(
        {"messages": [HumanMessage(content="第一轮")]},
        context=_context(),
        config=config,
    )
    seen.clear()
    graph.invoke(
        {"messages": [HumanMessage(content="第二轮")]},
        context=_context(),
        config=config,
    )
    assert seen == [None]


def test_role_id_from_context_not_checkpoint() -> None:
    """RAG retrieval must use the current invoke's role_id, not a stale checkpoint value."""
    set_router_classifier(lambda _prompt: '{"need_rag": true}')
    role_ids: list[str] = []

    def _track_retrieve(role_id: str, query: str, **kwargs):  # type: ignore[no-untyped-def]
        role_ids.append(role_id)
        return []

    import rag.retriever as retriever_mod

    retriever_mod.retrieve = _track_retrieve

    graph = compile_graph(checkpointer=MemorySaver(), use_pooled_postgres=False)
    config = {"configurable": {"thread_id": "thread-role-ctx"}}
    graph.invoke(
        {"messages": [HumanMessage(content="问政策")]},
        context=_context(role_id="role-a"),
        config=config,
    )
    graph.invoke(
        {"messages": [HumanMessage(content="再问")]},
        context=_context(role_id="role-b"),
        config=config,
    )
    assert role_ids == ["role-a", "role-b"]
