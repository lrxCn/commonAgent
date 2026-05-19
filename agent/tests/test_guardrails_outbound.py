"""Outbound guardrails — unit tests and graph integration."""

from __future__ import annotations

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.memory import MemorySaver

from gateway.schemas import RequestContext
from graph.build import compile_graph
from graph.context import graph_context_from_request
from graph.supervisor import reset_supervisor_overrides, set_supervisor_invoke
from guardrails.outbound import (
    OUTBOUND_SAFE_REPLY,
    OUTBOUND_TEST_SAMPLE,
    check_outbound,
    register_outbound_hook,
)
from guardrails.types import GuardResult
from settings.config import Settings, reset_settings, set_settings_override

_REQUIRED = {
    "LANGSMITH_API_KEY": "lsv2_test",
    "OPENAI_API_KEY": "sk-test",
    "DATABASE_URL": "postgresql://postgres:test@localhost:5432/common_agent",
}

_TEST_SETTINGS = Settings(
    LANGSMITH_API_KEY="lsv2_test",
    OPENAI_API_KEY="sk-test",
    DATABASE_URL=_REQUIRED["DATABASE_URL"],
    GUARDRAILS_ENABLED=True,
    MEM0_MOCK=True,
    QDRANT_MOCK=True,
    RAG_ROUTER_MODE="rules",
)


@pytest.fixture(autouse=True)
def _reset_hook(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("graph.nodes.load_thread_messages", lambda _thread_id: [])
    monkeypatch.setattr("graph.nodes.get_rolling_summary", lambda _thread_id: None)
    monkeypatch.setattr("graph.nodes.schedule_post_turn_jobs", lambda **_kwargs: None)
    register_outbound_hook(None)
    reset_supervisor_overrides()
    reset_settings()
    yield
    register_outbound_hook(None)
    reset_supervisor_overrides()
    reset_settings()


@pytest.fixture
def settings_enabled() -> Settings:
    set_settings_override(_TEST_SETTINGS)
    return _TEST_SETTINGS


def test_check_outbound_allows_normal_text(settings_enabled: Settings) -> None:
    result = check_outbound("今天可以帮您查询报销进度。", settings=settings_enabled)
    assert result.allowed is True
    assert result.reason_code is None


def test_check_outbound_blocks_test_sample(settings_enabled: Settings) -> None:
    result = check_outbound(OUTBOUND_TEST_SAMPLE, settings=settings_enabled)
    assert result.allowed is False
    assert result.reason_code == "policy_violation"
    assert result.message == OUTBOUND_SAFE_REPLY


def test_check_outbound_skipped_when_disabled() -> None:
    disabled = Settings(
        LANGSMITH_API_KEY="lsv2_test",
        OPENAI_API_KEY="sk-test",
        DATABASE_URL=_REQUIRED["DATABASE_URL"],
        GUARDRAILS_ENABLED=False,
    )
    result = check_outbound(OUTBOUND_TEST_SAMPLE, settings=disabled)
    assert result.allowed is True


def test_optional_hook_can_block_without_rules(settings_enabled: Settings) -> None:
    def hook(text: str) -> GuardResult | None:
        if text == "hook-block-outbound":
            return GuardResult.block(reason_code="content_blocked", message="Hook blocked.")
        return None

    register_outbound_hook(hook)
    assert check_outbound("safe reply", settings=settings_enabled).allowed is True
    blocked = check_outbound("hook-block-outbound", settings=settings_enabled)
    assert blocked.allowed is False
    assert blocked.reason_code == "content_blocked"


def test_hook_exception_returns_safe_reply(settings_enabled: Settings) -> None:
    def bad_hook(_text: str) -> GuardResult | None:
        raise RuntimeError("hook failed")

    register_outbound_hook(bad_hook)
    result = check_outbound("anything", settings=settings_enabled)
    assert result.allowed is False
    assert result.message == OUTBOUND_SAFE_REPLY


def test_graph_replaces_violating_supervisor_output(settings_enabled: Settings) -> None:
    set_supervisor_invoke(
        lambda _system, _messages: [AIMessage(content=OUTBOUND_TEST_SAMPLE)]
    )

    graph = compile_graph(checkpointer=MemorySaver(), use_pooled_postgres=False)
    result = graph.invoke(
        {"messages": [HumanMessage(content="你好")]},
        context=graph_context_from_request(
            RequestContext(user_id="u1", role_id="role-sales", tools=[])
        ),
        config={"configurable": {"thread_id": "thread-outbound-block"}},
    )

    assert result.get("outbound_blocked") is True
    ai_texts = [
        str(m.content)
        for m in (result.get("messages") or [])
        if isinstance(m, AIMessage)
    ]
    assert OUTBOUND_TEST_SAMPLE not in ai_texts
    assert any(OUTBOUND_SAFE_REPLY in text for text in ai_texts)


def test_graph_passes_clean_supervisor_output(settings_enabled: Settings) -> None:
    set_supervisor_invoke(
        lambda _system, _messages: [AIMessage(content="mock-reply:clean")]
    )

    graph = compile_graph(checkpointer=MemorySaver(), use_pooled_postgres=False)
    result = graph.invoke(
        {"messages": [HumanMessage(content="你好")]},
        context=graph_context_from_request(
            RequestContext(user_id="u1", role_id="role-sales", tools=[])
        ),
        config={"configurable": {"thread_id": "thread-outbound-pass"}},
    )

    assert result.get("outbound_blocked") is False
    ai_texts = [
        str(m.content)
        for m in (result.get("messages") or [])
        if isinstance(m, AIMessage)
    ]
    assert any("mock-reply:clean" in text for text in ai_texts)
