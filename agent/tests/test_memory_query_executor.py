"""Memory query executor behavior."""

from __future__ import annotations

from unittest.mock import MagicMock

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.memory import MemorySaver
import pytest

from gateway.schemas import RequestContext
from graph.build import compile_graph
from graph.context import graph_context_from_request
from graph.supervisor import reset_supervisor_overrides, set_supervisor_invoke
from memory.history import set_history_checkpointer
from memory.query import MISSING_MEMORY_REPLY, answer_memory_query
import rag.retriever as retriever_mod
from rag.retriever import reset_retriever_overrides
from rag.rewrite import set_rewrite_llm
from rag.router import set_router_classifier
from settings.config import Settings, reset_settings, set_settings_override

_ORIGINAL_RETRIEVE = retriever_mod.retrieve

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
    monkeypatch.setattr("graph.nodes.fetch_user_memories", lambda _user_id: [])
    monkeypatch.setattr("graph.nodes.schedule_post_turn_jobs", lambda **_kwargs: None)
    set_rewrite_llm(MagicMock(return_value="rewritten"))
    set_router_classifier(MagicMock(return_value='{"need_rag": true}'))
    reset_retriever_overrides()
    reset_supervisor_overrides()
    set_supervisor_invoke(MagicMock(return_value=[AIMessage(content="supervisor reply")]))
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


def _context() -> dict[str, object]:
    return graph_context_from_request(
        RequestContext(user_id="user-1", role_id="role-sales", tools=[])
    )


def _invoke(message: str, *, thread_id: str = "thread-memory-query") -> dict:
    graph = compile_graph(checkpointer=MemorySaver(), use_pooled_postgres=False)
    return graph.invoke(
        {"messages": [HumanMessage(content=message)]},
        context=_context(),
        config={"configurable": {"thread_id": thread_id}},
    )


def test_memory_query_answers_name_from_profile() -> None:
    result = answer_memory_query("我叫什么", mem0_memories=["用户叫刘日兴"])

    assert result.reply == "我记录到你叫刘日兴。"
    assert result.missing_reason == ""
    assert result.evidence[0].source == "memory_profile"
    assert result.evidence[0].field == "name"


def test_memory_query_missing_memory_is_honest() -> None:
    result = answer_memory_query("我是谁", mem0_memories=[])

    assert result.reply == MISSING_MEMORY_REPLY
    assert result.evidence == ()
    assert result.missing_reason == "missing_memory_profile"


def test_memory_query_latest_profile_value_wins_for_conflict() -> None:
    result = answer_memory_query(
        "我叫什么",
        mem0_memories=["用户叫张三", "用户叫李四"],
    )

    assert result.reply == "我记录到你叫李四。"


def test_memory_query_answers_company_address() -> None:
    result = answer_memory_query("我公司在哪", mem0_memories=["我公司在天翔街188号"])

    assert result.reply == "我记录到你公司的地址是天翔街188号。"
    assert result.evidence[0].field == "company_address"


def test_memory_query_answers_preference_from_free_text() -> None:
    result = answer_memory_query("我喜欢什么", mem0_memories=["用户喜欢周五下午安排复盘"])

    assert "周五下午安排复盘" in result.reply
    assert result.evidence[0].field == "preference"


def test_memory_query_can_use_prior_thread_user_statement() -> None:
    result = answer_memory_query(
        "我叫什么",
        mem0_memories=[],
        messages=[
            HumanMessage(content="我叫王五"),
            AIMessage(content="已收到"),
            HumanMessage(content="我叫什么"),
        ],
    )

    assert result.reply == "我记录到你叫王五。"
    assert result.evidence[0].source == "thread_memory"


def test_memory_query_graph_skips_rag_deepagents_and_mem0_write(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rewrite = MagicMock(return_value="rewritten")
    router = MagicMock(return_value='{"need_rag": true}')
    retrieve = MagicMock(return_value=[])
    supervisor = MagicMock(return_value=[AIMessage(content="supervisor reply")])
    schedule = MagicMock()
    set_rewrite_llm(rewrite)
    set_router_classifier(router)
    set_supervisor_invoke(supervisor)
    retriever_mod.retrieve = retrieve
    monkeypatch.setattr("graph.nodes.fetch_user_memories", lambda _user_id: ["用户叫刘日兴"])
    monkeypatch.setattr("graph.nodes.schedule_post_turn_jobs", schedule)

    result = _invoke("我是谁")

    assert result["intent_decision"].route == "memory_query"
    assert result["executor"] == "memory_query_executor"
    assert result["executor_reason"] == "turn_type_memory_query"
    assert "刘日兴" in str(result["messages"][-1].content)
    assert rewrite.call_count == 0
    assert router.call_count == 0
    assert retrieve.call_count == 0
    assert supervisor.call_count == 0
    assert schedule.call_count == 0
    assert result["path_metrics"]["post_turn_scheduled"] is False
