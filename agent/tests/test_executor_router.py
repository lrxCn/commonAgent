"""Executor router and graph gating tests."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.memory import MemorySaver

from gateway.schemas import RequestContext, ToolSpec
from graph.build import compile_graph
from graph.context import graph_context_from_request
from graph.executors import ExecutorType, build_simple_client_action, choose_executor
from graph.supervisor import (
    reset_supervisor_overrides,
    set_answer_invoke,
    set_supervisor_invoke,
)
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
}

_JUMP_TOOL = ToolSpec(
    name="jumpPage",
    description="Navigate to a page.",
    parameters={
        "type": "object",
        "properties": {"page": {"type": "string"}},
        "required": ["page"],
    },
    requires_approval=False,
)


@pytest.fixture(autouse=True)
def _graph_mocks(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("graph.nodes.load_thread_messages", lambda _thread_id: [])
    monkeypatch.setattr("graph.nodes.get_rolling_summary", lambda _thread_id: None)
    monkeypatch.setattr("graph.nodes.schedule_post_turn_jobs", lambda **_kwargs: None)
    set_rewrite_llm(lambda _prompt: "rewritten query text")
    set_router_classifier(None)
    reset_retriever_overrides()
    reset_supervisor_overrides()
    set_history_checkpointer(None)
    reset_settings()
    set_settings_override(Settings(**_REQUIRED_ENV))  # type: ignore[arg-type]
    yield
    set_rewrite_llm(None)
    set_router_classifier(None)
    reset_retriever_overrides()
    retriever_mod.retrieve = _ORIGINAL_RETRIEVE
    reset_supervisor_overrides()
    set_history_checkpointer(None)
    reset_settings()


def _context(*, tools: list[ToolSpec] | None = None) -> dict[str, object]:
    return graph_context_from_request(
        RequestContext(user_id="user-1", role_id="role-sales", tools=tools or [])
    )


def _invoke(message: str, *, thread_id: str, tools: list[ToolSpec] | None = None) -> dict:
    graph = compile_graph(checkpointer=MemorySaver(), use_pooled_postgres=False)
    return graph.invoke(
        {"messages": [HumanMessage(content=message)]},
        context=_context(tools=tools),
        config={"configurable": {"thread_id": thread_id}},
    )


def test_choose_executor_rag_answer_for_simple_knowledge_with_chunks() -> None:
    decision = choose_executor(
        turn_type="knowledge_query",
        user_message="报销制度是什么？",
        rag_skipped=False,
        rag_chunks=[RagChunk(doc_id="doc-1", chunk_id="c-1", text="policy", score=0.9)],
    )

    assert decision.executor is ExecutorType.RAG_ANSWER
    assert decision.reason.startswith("rag_chunks_available")


def test_choose_executor_deepagents_for_complex_task() -> None:
    decision = choose_executor(
        turn_type="knowledge_query",
        user_message="请分析报销制度并制定一个落地计划",
        rag_skipped=False,
        rag_chunks=[RagChunk(doc_id="doc-1", chunk_id="c-1", text="policy", score=0.9)],
    )

    assert decision.executor is ExecutorType.DEEPAGENTS
    assert decision.reason == "complex_knowledge_task"


def test_build_simple_client_action_extracts_page() -> None:
    action = build_simple_client_action("打开学生管理", [_JUMP_TOOL])

    assert action is not None
    assert action.tool == "jumpPage"
    assert action.args == {"page": "students"}


@pytest.mark.parametrize(
    ("message", "expected_page"),
    [
        ("打开学生管理", "students"),
        ("跳转到首页", "home"),
        ("前往 /app/admin/kb", "admin-kb"),
        ("打开 pageA", "pageA"),
    ],
)
def test_build_simple_client_action_catalog_and_legacy(
    message: str,
    expected_page: str,
) -> None:
    action = build_simple_client_action(message, [_JUMP_TOOL])

    assert action is not None
    assert action.args == {"page": expected_page}


def test_rag_answer_executor_does_not_call_deepagents() -> None:
    deepagents = MagicMock(return_value=[AIMessage(content="deepagents reply")])
    answer = MagicMock(return_value="answer executor reply")
    set_supervisor_invoke(deepagents)
    set_answer_invoke(answer)
    retriever_mod.retrieve = lambda *_args, **_kwargs: [
        RagChunk(doc_id="doc-1", chunk_id="c-1", text="policy", score=0.92)
    ]

    result = _invoke("报销制度是什么？", thread_id="executor-rag-answer")

    assert result.get("executor") == "rag_answer_executor"
    assert answer.call_count == 1
    assert deepagents.call_count == 0
    assert "answer executor reply" in [
        str(message.content)
        for message in result.get("messages") or []
        if isinstance(message, AIMessage)
    ]


def test_complex_task_uses_deepagents_executor() -> None:
    deepagents = MagicMock(return_value=[AIMessage(content="deepagents reply")])
    answer = MagicMock(return_value="answer executor reply")
    set_supervisor_invoke(deepagents)
    set_answer_invoke(answer)
    retriever_mod.retrieve = lambda *_args, **_kwargs: [
        RagChunk(doc_id="doc-1", chunk_id="c-1", text="policy", score=0.92)
    ]

    result = _invoke("请分析报销制度并制定一个落地计划", thread_id="executor-deepagents")

    assert result.get("executor") == "deepagents_executor"
    assert result.get("executor_reason") == "complex_knowledge_task"
    assert deepagents.call_count == 1
    assert answer.call_count == 0


def test_simple_client_action_executor_skips_deepagents() -> None:
    deepagents = MagicMock(return_value=[AIMessage(content="deepagents reply")])
    answer = MagicMock(return_value="answer executor reply")
    set_supervisor_invoke(deepagents)
    set_answer_invoke(answer)

    result = _invoke("打开学生管理", thread_id="executor-action", tools=[_JUMP_TOOL])

    actions = result.get("client_actions") or []
    assert result.get("executor") == "action_executor"
    assert len(actions) == 1
    assert actions[0].tool == "jumpPage"
    assert actions[0].args == {"page": "students"}
    assert result.get("path_metrics", {}).get("supervisor") == {
        "should_call": False,
        "called": False,
    }
    assert deepagents.call_count == 0
    assert answer.call_count == 0
