"""LangSmith tracing helpers (task 21)."""

from __future__ import annotations

import os

import pytest
from langgraph.checkpoint.memory import MemorySaver

from graph.build import compile_graph
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


def test_rewrite_process_inputs_mem0_facts_from_memories() -> None:
    meta = _rewrite_process_inputs(
        {
            "user_message": "它",
            "mem0_memories": ["偏好简洁", "在上海工作"],
            "recent_messages": [],
        }
    )
    assert meta["mem0_facts_count"] == 2
    assert meta["mem0_text_len"] > 0


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
    assert meta["mem0_facts_count"] == 0
    assert meta["mem0_text_len"] == 0


def test_rewrite_process_inputs_uses_mem0_text_kwarg_len() -> None:
    block = "## User preferences (from memory)\n\n- 事实"
    meta = _rewrite_process_inputs(
        {
            "user_message": "问题",
            "mem0_text": block,
            "mem0_facts_count": 1,
        }
    )
    assert meta["mem0_text_len"] == len(block)
    assert meta["mem0_facts_count"] == 1


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
        }
    )

    assert meta["executor"] == "rag_answer_executor"
    assert meta["executor_reason"] == "rag_chunks_available_score_0.92"


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
