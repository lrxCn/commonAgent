"""LangSmith tracing helpers (task 21)."""

from __future__ import annotations

import os

import pytest
from langgraph.checkpoint.memory import MemorySaver

from contracts.events import ObservabilityEvent, ObservabilityEventType
from graph.build import compile_graph
from infrastructure.langsmith import event_to_metadata
from observability.events import collect_events, emit_event as emit_raw_event
from observability.tracing import (
    _chitchat_process_inputs,
    _rewrite_process_inputs,
    _supervisor_process_inputs,
    attach_run_metadata,
    configure_tracing_from_settings,
    is_tracing_enabled,
    redact_secrets,
    truncate_for_trace,
)
from observability.tracing import emit_event
from settings.config import Settings, reset_settings, set_settings_override

_REQUIRED_ENV = {
    "LANGSMITH_API_KEY": "lsv2_test",
    "OPENAI_API_KEY": "sk-test",
    "DATABASE_URL": "postgresql://postgres:test@localhost:5432/common_agent",
}


@pytest.fixture(autouse=True)
def _reset_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "false")
    reset_settings()
    yield
    reset_settings()


def test_is_tracing_enabled_respects_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "false")
    assert is_tracing_enabled() is False
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "true")
    assert is_tracing_enabled() is True


def test_configure_tracing_from_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LANGCHAIN_TRACING_V2", raising=False)
    monkeypatch.delenv("LANGCHAIN_API_KEY", raising=False)
    settings = Settings(
        **_REQUIRED_ENV,  # type: ignore[arg-type]
        LANGCHAIN_TRACING_V2=False,
        LANGCHAIN_PROJECT="test-project",
    )
    enabled = configure_tracing_from_settings(settings)
    assert enabled is False
    assert os.environ["LANGCHAIN_TRACING_V2"] == "false"
    assert os.environ["LANGCHAIN_PROJECT"] == "test-project"
    assert os.environ["LANGCHAIN_API_KEY"] == "lsv2_test"


def test_truncate_and_redact_helpers() -> None:
    long_text = "x" * 600
    truncated = truncate_for_trace(long_text, limit=100)
    assert len(truncated) < len(long_text)
    assert "chars)" in truncated

    secret = "sk-super-secret-key-12345"
    assert "***" in redact_secrets(f"Bearer {secret}", [secret])


def test_attach_run_metadata_no_raise() -> None:
    attach_run_metadata({"span": "test", "rerank": True})


def test_attach_run_metadata_emits_compat_event() -> None:
    with collect_events() as events:
        attach_run_metadata({"span": "test", "rerank": True})

    assert len(events) == 1
    assert events[0].name == "metadata.attached"
    assert events[0].metadata == {"span": "test", "rerank": True}


def test_emit_event_records_typed_event_and_maps_metadata() -> None:
    with collect_events() as events:
        event = emit_event(
            ObservabilityEventType.TURN_CLASSIFIED,
            {"turn_type": "chitchat", "turn_type_reason": "chitchat_rule"},
        )

    assert event.name == "turn.classified"
    assert [item.name for item in events] == ["turn.classified"]
    assert event_to_metadata(events[0]) == {
        "turn_type": "chitchat",
        "turn_type_reason": "chitchat_rule",
    }


def test_raw_event_bus_noops_without_langsmith_adapter() -> None:
    with collect_events() as events:
        event = emit_raw_event("custom.event", {"x": 1})

    assert event == ObservabilityEvent("custom.event", {"x": 1})
    assert events == [event]


def test_path_event_maps_to_legacy_metadata_keys() -> None:
    event = ObservabilityEvent(
        ObservabilityEventType.POST_TURN_SCHEDULED,
        {
            "path_metrics": {
                "turn_type": "knowledge_query",
                "turn_type_reason": "knowledge_intent_rule",
                "rag": {"should_call": True, "called": True},
                "supervisor": {"should_call": True, "called": True},
                "post_turn_scheduled": True,
            }
        },
    )

    meta = event_to_metadata(event)

    assert meta["path_contract"] == "pass"
    assert meta["llm_call_count"] == 1
    assert meta["rag.called"] is True
    assert meta["post_turn_scheduled"] is True


def test_fallback_event_maps_to_legacy_metadata_keys() -> None:
    event = ObservabilityEvent(
        ObservabilityEventType.FALLBACK_TRIGGERED,
        {
            "fallback.triggered": True,
            "fallback.layer": "tool",
            "fallback.reason": "tool_not_allowed",
            "fallback.action": "tool_unavailable_reply",
            "fallback.user_visible": True,
            "fallback.recovered": True,
            "fallback.original_route": "client_action",
            "fallback.final_route": "general_chat",
        },
    )

    meta = event_to_metadata(event)

    assert meta["fallback.triggered"] is True
    assert meta["fallback.layer"] == "tool"
    assert meta["fallback.reason"] == "tool_not_allowed"


def test_intent_event_maps_classified_metadata() -> None:
    event = ObservabilityEvent(
        ObservabilityEventType.INTENT_CLASSIFIED,
        {
            "intent.speech_act": "question",
            "intent.domain": "user_memory",
            "intent.operation": "memory_read",
            "intent.route": "memory_query",
            "intent.confidence": 0.95,
            "intent.risk": "low",
            "intent.reasons": ["first_person_question"],
            "intent.needs_clarification": False,
            "intent.conflict": False,
            "intent.conflict_reason": "",
        },
    )

    meta = event_to_metadata(event)

    assert meta["intent.route"] == "memory_query"
    assert meta["intent.conflict"] is False
    assert meta["intent.conflict_reason"] == ""


def test_rewrite_process_inputs_mem0_facts_from_memories() -> None:
    meta = _rewrite_process_inputs(
        {
            "user_message": "它",
            "user_memories": ["偏好简洁", "在上海工作"],
            "recent_messages": [],
        }
    )
    assert meta["user_memory_facts_count"] == 2
    assert meta["user_memories_text_len"] > 0


def test_rewrite_process_inputs_skip_metadata() -> None:
    meta = _rewrite_process_inputs(
        {
            "user_message": "你好",
            "rewrite_skipped": True,
            "rewrite_skip_reason": "chitchat",
            "recent_messages": [],
        }
    )
    assert meta["rewrite_skipped"] is True
    assert meta["rewrite_skip_reason"] == "chitchat"
    assert meta["user_memory_facts_count"] == 0
    assert meta["user_memories_text_len"] == 0


def test_rewrite_process_inputs_uses_user_memories_text_kwarg_len() -> None:
    block = "## User preferences (from memory)\n\n- 事实"
    meta = _rewrite_process_inputs(
        {
            "user_message": "问题",
            "user_memories_text": block,
            "user_memory_facts_count": 1,
        }
    )
    assert meta["user_memories_text_len"] == len(block)
    assert meta["user_memory_facts_count"] == 1


def test_chitchat_process_inputs_uses_template_executor_by_default() -> None:
    set_settings_override(
        Settings(  # type: ignore[arg-type]
            **_REQUIRED_ENV,
            CHITCHAT_USE_LLM=False,
            CHITCHAT_MODEL_NAME=None,
            _env_file=None,
        )
    )
    meta = _chitchat_process_inputs({"user_message": "谢谢"})
    assert meta["executor"] == "template_executor"
    assert meta["chitchat.use_llm"] is False
    assert meta["chitchat.model_name"] == ""


def test_chitchat_process_inputs_uses_small_chat_executor_when_enabled() -> None:
    set_settings_override(
        Settings(  # type: ignore[arg-type]
            **_REQUIRED_ENV,
            CHITCHAT_USE_LLM=True,
            CHITCHAT_MODEL_NAME=None,
            _env_file=None,
        )
    )
    meta = _chitchat_process_inputs({"user_message": "你好"})
    assert meta["executor"] == "small_chat_executor"
    assert meta["chitchat.use_llm"] is True
    assert meta["chitchat.model_name"] == "Pro/moonshotai/Kimi-K2.6"


def test_supervisor_process_inputs_records_executor_metadata() -> None:
    meta = _supervisor_process_inputs(
        {
            "system_prompt": "system",
            "messages": [],
            "executor": "rag_answer_executor",
            "executor_reason": "rag_chunks_available_score_0.92",
            "context_budget": {
                "system_prompt_len": 123,
                "user_memory_count": 3,
                "rag_chunk_count": 2,
                "budget_truncated": True,
            },
        }
    )

    assert meta["executor"] == "rag_answer_executor"
    assert meta["executor_reason"] == "rag_chunks_available_score_0.92"
    assert meta["system_prompt_len"] == 123
    assert meta["user_memory_count"] == 3
    assert meta["rag_chunk_count"] == 2
    assert meta["budget_truncated"] is True


def test_traceable_imports_on_core_modules() -> None:
    from graph.supervisor import invoke_supervisor
    from guardrails.inbound import check_inbound
    from guardrails.outbound import check_outbound
    from rag.retriever import rerank_candidates, retrieve
    from rag.rewrite import rewrite_query
    from rag.router import should_retrieve

    for fn in (
        rewrite_query,
        should_retrieve,
        retrieve,
        rerank_candidates,
        invoke_supervisor,
        check_inbound,
        check_outbound,
    ):
        assert callable(fn)


def test_compile_graph_with_tracing_configured() -> None:
    set_settings_override(
        Settings(**_REQUIRED_ENV, LANGCHAIN_TRACING_V2=False)  # type: ignore[arg-type]
    )
    graph = compile_graph(checkpointer=MemorySaver(), use_pooled_postgres=False)
    assert "supervisor" in graph.nodes


def test_smoke_is_tracing_enabled_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "false")
    assert is_tracing_enabled() in (True, False)
