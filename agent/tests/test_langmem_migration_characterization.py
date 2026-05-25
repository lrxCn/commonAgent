"""Freeze mem0-era memory read/write behavior before langmem migration (task 69).

These tests document the baseline that tasks 70-74 must preserve or improve.
Production paths still use mem0; do not switch backends in this module.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.memory import MemorySaver

from contracts.memory_write import MemoryWriteExpectation, StructuredMemoryRecord
from gateway.schemas import RequestContext
from graph.build import compile_graph
from graph.context import graph_context_from_request
from graph.nodes import load_memory_node
from graph.supervisor import reset_supervisor_overrides, set_answer_invoke, set_supervisor_invoke
from intent.engine import classify_intent
from intent.signals import extract_signals
from memory.mem0_write import (
    extract_and_store,
    reset_mem0_write_overrides,
    set_mem0_add_fn,
)
from memory.store import reset_pooled_store
from memory.write import store_structured_record
from memory.post_turn import reset_post_turn_executor, schedule_post_turn_jobs
from memory.store import reset_pooled_store
from memory.structured_record import build_structured_memory_record
from settings.config import Settings, reset_settings, set_settings_override

_REQUIRED_ENV = {
    "LANGSMITH_API_KEY": "lsv2_test",
    "OPENAI_API_KEY": "sk-test",
    "DATABASE_URL": "postgresql://postgres:test@localhost:5432/common_agent",
    "GUARDRAILS_ENABLED": False,
    "MEM0_MOCK": True,
    "MEM0_LLM_MODEL_NAME": "Qwen/Qwen2.5-7B-Instruct",
    "QDRANT_MOCK": True,
    "RAG_ROUTER_MODE": "rules",
}

_SEED_PATH = Path(__file__).resolve().parents[1] / "evals" / "memory_write_seed.json"


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("graph.nodes.load_thread_messages", lambda _thread_id: [])
    monkeypatch.setattr("graph.nodes.get_rolling_summary", lambda _thread_id: None)
    reset_settings()
    reset_mem0_write_overrides()
    reset_post_turn_executor()
    reset_pooled_store()
    reset_supervisor_overrides()
    set_settings_override(Settings(**_REQUIRED_ENV))  # type: ignore[arg-type]
    set_supervisor_invoke(
        lambda _system, messages: [
            AIMessage(content=f"reply:{messages[-1].content}"),
        ]
    )
    set_answer_invoke(lambda _system, messages: f"reply:{messages[-1].content}")
    yield
    reset_post_turn_executor()
    reset_supervisor_overrides()
    reset_mem0_write_overrides()
    reset_pooled_store()
    reset_settings()


def _graph_context() -> dict[str, object]:
    return graph_context_from_request(
        RequestContext(user_id="user-baseline", role_id="role-1", tools=[]),
    )


def test_load_memory_node_produces_mem0_memories_and_parallel_checkpoint_reads(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Baseline: load_memory returns list[str] facts and fetches checkpoint summary."""
    load_messages = MagicMock(return_value=[HumanMessage(content="prior turn")])
    load_summary = MagicMock(return_value="rolling summary text")
    fetch_memories = MagicMock(return_value=["偏好简洁回答", "用户叫张三"])
    monkeypatch.setattr("graph.nodes.fetch_user_memories", fetch_memories)
    monkeypatch.setattr("graph.nodes.load_thread_messages", load_messages)
    monkeypatch.setattr("graph.nodes.get_rolling_summary", load_summary)

    runtime = MagicMock()
    runtime.context = {"user_id": "user-baseline", "role_id": "role-1", "tools": []}

    out = load_memory_node(
        {"messages": [HumanMessage(content="你好")]},
        runtime,
        {"configurable": {"thread_id": "thread-baseline-1"}},
    )

    fetch_memories.assert_called_once_with("user-baseline", query="你好")
    load_messages.assert_called_once_with("thread-baseline-1")
    load_summary.assert_called_once_with("thread-baseline-1")
    assert out["mem0_memories"] == ["偏好简洁回答", "用户叫张三"]
    assert isinstance(out["mem0_memories"], list)
    assert all(isinstance(item, str) for item in out["mem0_memories"])
    assert out["rolling_summary"] == "rolling summary text"


def test_post_turn_with_memory_write_record_calls_structured_write_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Baseline: structured record present → store_structured_record, not infer."""
    store_structured = MagicMock(
        return_value=MagicMock(status="stored", stored_count=1, reason="")
    )
    extract = MagicMock()
    monkeypatch.setattr("memory.post_turn.store_structured_record", store_structured)
    monkeypatch.setattr("memory.post_turn.extract_and_store", extract)
    monkeypatch.setattr("memory.post_turn.update_rolling_summary", lambda *_args, **_kwargs: None)

    graph = compile_graph(checkpointer=MemorySaver(), use_pooled_postgres=False)
    graph.invoke(
        {"messages": [HumanMessage(content="我出生于1997年")]},
        context=_graph_context(),
        config={"configurable": {"thread_id": "thread-structured-baseline"}},
    )

    store_structured.assert_called_once()
    extract.assert_not_called()


def test_post_turn_without_memory_write_record_calls_inferred_write(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Baseline: general chat → extract_and_store infer path."""
    store_structured = MagicMock()
    extract = MagicMock(
        return_value=MagicMock(status="stored", stored_count=1, reason="")
    )
    monkeypatch.setattr("memory.post_turn.store_structured_record", store_structured)
    monkeypatch.setattr("memory.post_turn.extract_and_store", extract)
    monkeypatch.setattr("memory.post_turn.update_rolling_summary", lambda *_args, **_kwargs: None)

    schedule_post_turn_jobs(
        thread_id="thread-inferred-baseline",
        user_id="user-baseline",
        turn_messages=[
            HumanMessage(content="hello"),
            AIMessage(content="reply:hello"),
        ],
        memory_write_record=None,
    ).result(timeout=10)

    extract.assert_called_once()
    store_structured.assert_not_called()


def test_memory_query_does_not_schedule_mem0_write(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Baseline: memory_query reads memories but never schedules post_turn writes."""
    schedule = MagicMock()
    monkeypatch.setattr("graph.nodes.fetch_user_memories", lambda _uid, **_kwargs: ["用户叫刘日兴"])
    monkeypatch.setattr("graph.nodes.schedule_post_turn_jobs", schedule)

    graph = compile_graph(checkpointer=MemorySaver(), use_pooled_postgres=False)
    result = graph.invoke(
        {"messages": [HumanMessage(content="我是谁")]},
        context=_graph_context(),
        config={"configurable": {"thread_id": "thread-memory-query-baseline"}},
    )

    assert result["intent_decision"].route == "memory_query"
    assert result["path_metrics"]["post_turn_scheduled"] is False
    assert schedule.call_count == 0


def test_fact_update_structured_seed_forbids_stored_empty() -> None:
    """Baseline policy: structured fact_update eval seeds forbid stored_empty."""
    rows = json.loads(_SEED_PATH.read_text(encoding="utf-8"))
    regression_rows = [
        row for row in rows if row["category"] == "regression_store_empty"
    ]
    assert regression_rows

    for row in regression_rows:
        expected = row["expected_write"]
        expectation = MemoryWriteExpectation(
            mode=expected["mode"],
            infer=expected["infer"],
            expected_record=(
                StructuredMemoryRecord.model_validate(expected["expected_record"])
                if expected.get("expected_record") is not None
                else None
            ),
            forbidden_final_status=tuple(expected.get("forbidden_final_status", ())),
        )
        assert expectation.mode == "structured"
        assert "stored_empty" in expectation.forbidden_final_status


def test_fact_update_structured_mock_path_does_not_return_stored_empty() -> None:
    """Baseline target: structured Store profile write stores canonical fact."""
    from langgraph.store.memory import InMemoryStore

    set_settings_override(
        Settings(
            **{
                **_REQUIRED_ENV,
                "MEM0_MOCK": False,
                "MEMORY_STORE_MOCK": False,
                "MEMORY_STORE_SETUP": False,
            }
        )
    )  # type: ignore[arg-type]
    store = InMemoryStore()
    from memory.store import set_store_factory

    set_store_factory(lambda: store)
    add_mock = MagicMock()
    set_mem0_add_fn(add_mock)

    user_text = "我叫张三"
    signals = extract_signals(user_text)
    decision = classify_intent(user_text)
    record = build_structured_memory_record(
        signals,
        decision,
        source_turn_id="thread-target:turn-1",
    )
    assert record is not None

    result = store_structured_record("user-fact-update", record)

    assert result.status == "stored"
    assert result.stored_count >= 1
    assert result.status != "stored_empty"
    add_mock.assert_not_called()
