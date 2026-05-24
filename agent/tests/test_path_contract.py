"""Path contract metrics for graph execution."""

from __future__ import annotations

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.memory import MemorySaver
import pytest

from gateway.schemas import RequestContext, ToolSpec
from graph.build import compile_graph
from graph.chitchat_executor import set_chitchat_llm
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
    "MEM0_MOCK": True,
    "QDRANT_MOCK": True,
    "RAG_ROUTER_MODE": "rules",
}


@pytest.fixture(autouse=True)
def _graph_mocks(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("graph.nodes.load_thread_messages", lambda _thread_id: [])
    monkeypatch.setattr("graph.nodes.get_rolling_summary", lambda _thread_id: None)
    monkeypatch.setattr("graph.nodes.schedule_post_turn_jobs", lambda **_kwargs: None)
    set_rewrite_llm(lambda _prompt: "rewritten query text")
    set_chitchat_llm(None)
    set_router_classifier(None)
    reset_retriever_overrides()
    reset_supervisor_overrides()
    set_history_checkpointer(None)
    reset_settings()
    set_settings_override(Settings(**_REQUIRED_ENV))  # type: ignore[arg-type]

    set_supervisor_invoke(
        lambda _system, _messages: [AIMessage(content="mock supervisor reply")]
    )
    set_answer_invoke(lambda _system, _messages: "mock supervisor reply")
    yield
    set_rewrite_llm(None)
    set_chitchat_llm(None)
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


def _context_with_tools(tools: list[ToolSpec]) -> dict[str, object]:
    return graph_context_from_request(
        RequestContext(user_id="user-1", role_id="role-sales", tools=tools)
    )


def _invoke(
    message: str,
    *,
    thread_id: str,
    tools: list[ToolSpec] | None = None,
) -> dict:
    graph = compile_graph(checkpointer=MemorySaver(), use_pooled_postgres=False)
    return graph.invoke(
        {"messages": [HumanMessage(content=message)]},
        context=_context_with_tools(tools) if tools else _context(),
        config={"configurable": {"thread_id": thread_id}},
    )


def test_fact_update_path_contract_skips_small_llms_and_rag() -> None:
    result = _invoke("我出生于1997年", thread_id="path-fact")

    metrics = result["path_metrics"]
    assert metrics["turn_type"] == "fact_update"
    assert metrics["fast_path"] is True
    assert metrics["path_contract"] == "pass"
    assert metrics["llm_call_count"] == 0
    assert metrics["rewrite"] == {"should_call": False, "called": False}
    assert metrics["rag_router"] == {"should_call": False, "called": False}
    assert metrics["rag"] == {"should_call": False, "called": False}
    assert metrics["supervisor"] == {"should_call": False, "called": False}


def test_chitchat_path_contract_skips_small_llms_and_rag() -> None:
    result = _invoke("你好", thread_id="path-chitchat")

    metrics = result["path_metrics"]
    assert metrics["turn_type"] == "chitchat"
    assert metrics["fast_path"] is True
    assert metrics["path_contract"] == "pass"
    assert metrics["llm_call_count"] == 0
    assert metrics["rewrite"] == {"should_call": False, "called": False}
    assert metrics["rag_router"] == {"should_call": False, "called": False}
    assert metrics["rag"] == {"should_call": False, "called": False}
    assert metrics["supervisor"] == {"should_call": False, "called": False}


def test_memory_query_path_contract_skips_rag_and_models(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("graph.nodes.fetch_user_memories", lambda _user_id: ["用户叫刘日兴"])
    result = _invoke("我是谁", thread_id="path-memory-query")

    metrics = result["path_metrics"]
    assert result["executor"] == "memory_query_executor"
    assert metrics["path_contract"] == "pass"
    assert metrics["fast_path"] is True
    assert metrics["post_turn_scheduled"] is False
    assert metrics["llm_call_count"] == 0
    assert metrics["rewrite"] == {"should_call": False, "called": False}
    assert metrics["rag_router"] == {"should_call": False, "called": False}
    assert metrics["rag"] == {"should_call": False, "called": False}
    assert metrics["supervisor"] == {"should_call": False, "called": False}


def test_knowledge_query_path_contract_runs_rag_without_router_llm() -> None:
    retriever_mod.retrieve = lambda *_args, **_kwargs: [
        RagChunk(doc_id="doc-1", chunk_id="c-1", text="policy", score=0.92)
    ]

    result = _invoke("报销制度是什么？", thread_id="path-knowledge")

    metrics = result["path_metrics"]
    assert metrics["turn_type"] == "knowledge_query"
    assert metrics["path_contract"] == "pass"
    assert metrics["llm_call_count"] == 1
    assert metrics["rewrite"] == {"should_call": False, "called": False}
    assert metrics["rag_router"] == {"should_call": False, "called": False}
    assert metrics["rag"] == {"should_call": True, "called": True}
    assert metrics["supervisor"] == {"should_call": True, "called": True}


def test_client_action_path_contract_uses_action_executor_without_model() -> None:
    result = _invoke("打开 pageA", thread_id="path-client-action", tools=[_JUMP_TOOL])

    metrics = result["path_metrics"]
    actions = result.get("client_actions") or []
    assert result["turn_type"] == "client_action"
    assert result["executor"] == "action_executor"
    assert result["executor_reason"] == "simple_client_action"
    assert actions[0].tool == "jumpPage"
    assert actions[0].args == {"page": "pageA"}
    assert metrics["path_contract"] == "pass"
    assert metrics["llm_call_count"] == 0
    assert metrics["rewrite"] == {"should_call": False, "called": False}
    assert metrics["rag_router"] == {"should_call": False, "called": False}
    assert metrics["rag"] == {"should_call": False, "called": False}
    assert metrics["supervisor"] == {"should_call": False, "called": False}


def test_ambiguous_with_tools_path_contract_uses_deepagents() -> None:
    result = _invoke("继续", thread_id="path-ambiguous-tools", tools=[_JUMP_TOOL])

    metrics = result["path_metrics"]
    assert result["turn_type"] == "ambiguous"
    assert result["executor"] == "deepagents_executor"
    assert result["executor_reason"] == "ambiguous_with_tools"
    assert metrics["path_contract"] == "pass"
    assert metrics["llm_call_count"] == 2
    assert metrics["rewrite"] == {"should_call": True, "called": True}
    assert metrics["rag_router"] == {"should_call": False, "called": False}
    assert metrics["rag"] == {"should_call": True, "called": True}
    assert metrics["supervisor"] == {"should_call": True, "called": True}


def test_chitchat_fast_path_wins_over_rewrite_force() -> None:
    settings = Settings(  # type: ignore[arg-type]
        **_REQUIRED_ENV,
        REWRITE_FORCE=True,
    )
    set_settings_override(settings)

    result = _invoke("你好", thread_id="path-rewrite-force-fail")

    metrics = result["path_metrics"]
    assert metrics["path_contract"] == "pass"
    assert metrics["fast_path"] is True
    assert metrics["llm_call_count"] == 0
    assert metrics["rewrite"] == {"should_call": False, "called": False}


def test_chitchat_small_model_path_contract_records_executor_llm() -> None:
    settings = Settings(  # type: ignore[arg-type]
        **_REQUIRED_ENV,
        CHITCHAT_USE_LLM=True,
    )
    set_settings_override(settings)
    set_chitchat_llm(lambda _prompt: "你好呀。")

    result = _invoke("你好", thread_id="path-chitchat-small-llm")

    metrics = result["path_metrics"]
    assert metrics["turn_type"] == "chitchat"
    assert metrics["path_contract"] == "pass"
    assert metrics["llm_call_count"] == 1
    assert metrics["rewrite"] == {"should_call": False, "called": False}
    assert metrics["rag_router"] == {"should_call": False, "called": False}
    assert metrics["rag"] == {"should_call": False, "called": False}
    assert metrics["supervisor"] == {"should_call": True, "called": True}
