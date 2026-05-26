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
from memory.query import (
    MISSING_MEMORY_REPLY,
    MemoryQueryEvidence,
    MemoryQueryResult,
    answer_memory_query,
    memory_query_trace_metadata,
)
from memory.query_polish import set_memory_query_polish_llm
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
    "MEMORY_STORE_MOCK": True,
    "QDRANT_MOCK": True,
    "RAG_ROUTER_MODE": "rules",
}


@pytest.fixture(autouse=True)
def _graph_mocks(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("graph.nodes.load_thread_messages", lambda _thread_id: [])
    monkeypatch.setattr("graph.nodes.get_rolling_summary", lambda _thread_id: None)
    monkeypatch.setattr("graph.nodes.fetch_user_memories", lambda _user_id, **_kwargs: [])
    monkeypatch.setattr("graph.nodes.schedule_post_turn_jobs", lambda **_kwargs: None)
    set_rewrite_llm(MagicMock(return_value="rewritten"))
    set_router_classifier(MagicMock(return_value='{"need_rag": true}'))
    reset_retriever_overrides()
    reset_supervisor_overrides()
    set_supervisor_invoke(MagicMock(return_value=[AIMessage(content="supervisor reply")]))
    set_history_checkpointer(None)
    set_memory_query_polish_llm(None)
    reset_settings()
    set_settings_override(Settings(**_REQUIRED_ENV))  # type: ignore[arg-type]
    yield
    set_rewrite_llm(None)
    set_router_classifier(None)
    reset_retriever_overrides()
    retriever_mod.retrieve = _ORIGINAL_RETRIEVE
    reset_supervisor_overrides()
    set_history_checkpointer(None)
    set_memory_query_polish_llm(None)
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
    result = answer_memory_query("我叫什么", user_memories=["用户叫刘日兴"])

    assert result.reply == "我记录到你叫刘日兴。"
    assert result.missing_reason == ""
    assert result.evidence[0].source == "memory_profile"
    assert result.evidence[0].field == "name"


def test_memory_query_missing_memory_is_honest() -> None:
    result = answer_memory_query("我是谁", user_memories=[])

    assert result.reply == MISSING_MEMORY_REPLY
    assert result.evidence == ()
    assert result.missing_reason == "missing_memory_profile"


def test_memory_query_latest_profile_value_wins_for_conflict() -> None:
    result = answer_memory_query(
        "我叫什么",
        user_memories=["用户叫张三", "用户叫李四"],
    )

    assert result.reply == "我记录到你叫李四。"


def test_memory_query_answers_company_address() -> None:
    result = answer_memory_query("我公司在哪", user_memories=["我公司在天翔街188号"])

    assert result.reply == "我记录到你公司的地址是天翔街188号。"
    assert result.evidence[0].field == "company_address"


def test_memory_query_answers_preference_from_free_text() -> None:
    result = answer_memory_query("我喜欢什么", user_memories=["用户喜欢周五下午安排复盘"])

    assert "周五下午安排复盘" in result.reply
    assert result.evidence[0].field == "preference"


def test_memory_query_can_use_prior_thread_user_statement() -> None:
    result = answer_memory_query(
        "我叫什么",
        user_memories=[],
        messages=[
            HumanMessage(content="我叫王五"),
            AIMessage(content="已收到"),
            HumanMessage(content="我叫什么"),
        ],
    )

    assert result.reply == "我记录到你叫王五。"
    assert result.evidence[0].source == "thread_memory"


def test_memory_query_graph_skips_rag_deepagents_and_memory_write(
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
    monkeypatch.setattr("graph.nodes.fetch_user_memories", lambda _user_id, **_kwargs: ["用户叫刘日兴"])
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


def test_memory_query_graph_records_missing_memory_fallback() -> None:
    result = _invoke("我是谁", thread_id="thread-memory-missing-fallback")

    assert result["messages"][-1].content == MISSING_MEMORY_REPLY
    assert result["path_metrics"]["fallback_count"] == 1
    assert result["path_metrics"]["fallback_layer"] == "memory"
    assert result["path_metrics"]["fallback_reason"] == "missing_memory_profile"
    assert result["path_metrics"]["fallback_action"] == "honest_missing_memory"
    assert result["path_metrics"]["fallback_user_visible"] is True


def test_memory_query_characterization_name_evidence_and_trace() -> None:
    result = answer_memory_query("我叫什么", user_memories=["用户叫刘日兴"])

    assert result == MemoryQueryResult(
        reply="我记录到你叫刘日兴。",
        evidence=(
            MemoryQueryEvidence(
                source="memory_profile",
                field="name",
                value="刘日兴",
                text="姓名: 刘日兴",
            ),
        ),
        missing_reason="",
    )
    assert memory_query_trace_metadata(result) == {
        "memory_query.evidence_count": 1,
        "memory_query.evidence_sources": ["memory_profile"],
        "memory_query.evidence_fields": ["name"],
        "memory_query.missing_reason": "",
    }


def test_memory_query_characterization_company_address() -> None:
    result = answer_memory_query("我公司在哪", user_memories=["我公司在天翔街188号"])

    assert result.reply == "我记录到你公司的地址是天翔街188号。"
    assert result.missing_reason == ""
    assert result.evidence == (
        MemoryQueryEvidence(
            source="memory_profile",
            field="company_address",
            value="天翔街188号",
            text="公司地址: 天翔街188号",
        ),
    )


def test_memory_query_characterization_preference_free_text() -> None:
    result = answer_memory_query("我喜欢什么", user_memories=["用户喜欢周五下午安排复盘"])

    assert result.reply == "我记录到：用户喜欢周五下午安排复盘。"
    assert result.missing_reason == ""
    assert result.evidence[0].field == "preference"
    assert result.evidence[0].source == "memory_free_text"
    assert result.evidence[0].value == "用户喜欢周五下午安排复盘"


def test_memory_query_characterization_missing_name_reply_and_reason() -> None:
    result = answer_memory_query("我叫什么", user_memories=[])

    assert result.reply == (
        "我目前没有可靠记录你的姓名。你可以告诉我你的名字，我之后会按你的授权记住。"
    )
    assert result.evidence == ()
    assert result.missing_reason == "missing_name"


def test_memory_query_characterization_missing_profile_reply_and_reason() -> None:
    result = answer_memory_query("我是谁", user_memories=[])

    assert result.reply == MISSING_MEMORY_REPLY
    assert result.evidence == ()
    assert result.missing_reason == "missing_memory_profile"


def test_memory_query_characterization_thread_fallback_source() -> None:
    result = answer_memory_query(
        "我叫什么",
        user_memories=[],
        messages=[
            HumanMessage(content="我叫王五"),
            AIMessage(content="已收到"),
            HumanMessage(content="我叫什么"),
        ],
    )

    assert result.reply == "我记录到你叫王五。"
    assert result.evidence == (
        MemoryQueryEvidence(
            source="thread_memory",
            field="name",
            value="王五",
            text="姓名: 王五",
        ),
    )
    assert result.missing_reason == ""


def test_memory_query_characterization_full_profile_multi_evidence() -> None:
    result = answer_memory_query(
        "我是谁",
        user_memories=["用户叫刘日兴", "用户是产品经理", "用户在北京"],
    )

    assert result.reply == "根据可靠记忆，我记录到：你叫刘日兴；你是产品经理。"
    assert [item.field for item in result.evidence] == ["name", "job"]
    assert all(item.source == "memory_profile" for item in result.evidence)
    assert result.missing_reason == ""


def test_memory_query_graph_appends_single_assistant_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("graph.nodes.fetch_user_memories", lambda _user_id, **_kwargs: ["用户叫刘日兴"])
    result = _invoke("我叫什么", thread_id="thread-memory-single-ai")

    ai_messages = [message for message in result["messages"] if isinstance(message, AIMessage)]
    assert len(ai_messages) == 1
    assert ai_messages[0].content == "我记录到你叫刘日兴。"


def test_memory_query_graph_polish_disabled_passthrough(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("graph.nodes.fetch_user_memories", lambda _user_id, **_kwargs: ["用户叫刘日兴"])
    result = _invoke("我叫什么", thread_id="thread-memory-polish-disabled")

    assert result["messages"][-1].content == "我记录到你叫刘日兴。"
    assert result["path_metrics"]["memory_query_polish.enabled"] is False
    assert result["path_metrics"]["memory_query_polish.used_llm"] is False
    assert result["path_metrics"]["memory_query_polish.fallback_reason"] == "disabled"
    assert result["path_metrics"]["memory_query_polish.changed"] is False


def test_memory_query_graph_polish_enabled_uses_mock_llm(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("graph.nodes.fetch_user_memories", lambda _user_id, **_kwargs: ["用户叫刘日兴"])
    reset_settings()
    set_settings_override(
        Settings(**{**_REQUIRED_ENV, "MEMORY_QUERY_POLISH_USE_LLM": True})  # type: ignore[arg-type]
    )
    mock = MagicMock()
    mock.invoke.return_value = MagicMock(content="我记得你的名字是刘日兴。")
    set_memory_query_polish_llm(mock)

    result = _invoke("我叫什么", thread_id="thread-memory-polish-enabled")

    assert result["messages"][-1].content == "我记得你的名字是刘日兴。"
    assert result["path_metrics"]["memory_query_polish.enabled"] is True
    assert result["path_metrics"]["memory_query_polish.used_llm"] is True
    assert result["path_metrics"]["memory_query_polish.fallback_reason"] == ""
    assert result["path_metrics"]["memory_query_polish.changed"] is True
    mock.invoke.assert_called_once()


def test_memory_query_graph_polish_validation_failure_falls_back(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("graph.nodes.fetch_user_memories", lambda _user_id, **_kwargs: ["用户叫刘日兴"])
    reset_settings()
    set_settings_override(
        Settings(**{**_REQUIRED_ENV, "MEMORY_QUERY_POLISH_USE_LLM": True})  # type: ignore[arg-type]
    )
    mock = MagicMock()
    mock.invoke.return_value = MagicMock(content="你叫王五。")
    set_memory_query_polish_llm(mock)

    result = _invoke("我叫什么", thread_id="thread-memory-polish-fallback")

    assert result["messages"][-1].content == "我记录到你叫刘日兴。"
    assert result["path_metrics"]["memory_query_polish.used_llm"] is True
    assert result["path_metrics"]["memory_query_polish.fallback_reason"] == "missing_evidence_value"
    assert result["path_metrics"]["memory_query_polish.changed"] is False
