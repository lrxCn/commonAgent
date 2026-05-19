"""End-to-end invoke tests for the Supervisor graph (mocked LLM / retriever)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.memory import MemorySaver

from gateway.schemas import RequestContext
from graph.build import compile_graph
from graph.supervisor import reset_supervisor_overrides, set_supervisor_invoke
from memory.history import set_history_checkpointer
from rag.retriever import RagChunk, reset_retriever_overrides
from rag.rewrite import set_rewrite_llm
from rag.router import set_router_classifier
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
def _mock_checkpoint_history(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("graph.nodes.load_thread_messages", lambda _thread_id: [])
    monkeypatch.setattr("graph.nodes.get_rolling_summary", lambda _thread_id: None)


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
    yield
    set_rewrite_llm(None)
    set_router_classifier(None)
    reset_retriever_overrides()
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
    return ctx.model_dump()


def test_invoke_appends_ai_message() -> None:
    graph = compile_graph(checkpointer=MemorySaver(), use_pooled_postgres=False)
    config = {"configurable": {"thread_id": "thread-mock-1"}}
    result = graph.invoke(
        {
            "messages": [HumanMessage(content="你好")],
            "user_message": "你好",
            "context": _context(),
        },
        config=config,
    )

    messages = result.get("messages") or []
    assert any(isinstance(message, AIMessage) for message in messages)
    ai_texts = [str(message.content) for message in messages if isinstance(message, AIMessage)]
    assert any("mock-reply" in text for text in ai_texts)
    assert result.get("rewritten_query") == "rewritten query text"
    assert result.get("rag_skipped") is True


def test_rag_skipped_does_not_call_retriever() -> None:
    retrieve_mock = MagicMock(return_value=[])
    import rag.retriever as retriever_mod

    retriever_mod.retrieve = retrieve_mock

    graph = compile_graph(checkpointer=MemorySaver(), use_pooled_postgres=False)
    graph.invoke(
        {
            "messages": [HumanMessage(content="你好")],
            "user_message": "你好",
            "context": _context(),
        },
        config={"configurable": {"thread_id": "thread-mock-2"}},
    )

    assert retrieve_mock.call_count == 0


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
        {
            "messages": [HumanMessage(content="报销制度是什么？")],
            "user_message": "报销制度是什么？",
            "context": _context(),
        },
        config={"configurable": {"thread_id": "thread-mock-3"}},
    )

    assert retrieve_mock.call_count == 1
    assert result.get("rag_skipped") is False
    chunks = result.get("rag_chunks") or []
    assert len(chunks) == 1
