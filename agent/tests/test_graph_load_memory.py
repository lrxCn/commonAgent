"""Unit tests for graph.nodes.load_memory_node (task 25)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from langchain_core.messages import HumanMessage

from graph.nodes import load_memory_node
from settings.config import Settings, reset_settings, set_settings_override

_REQUIRED_ENV = {
    "LANGSMITH_API_KEY": "lsv2_test",
    "OPENAI_API_KEY": "sk-test",
    "DATABASE_URL": "postgresql://postgres:test@localhost:5432/common_agent",
    "MEMORY_STORE_MOCK": True,
}


@pytest.fixture(autouse=True)
def _settings() -> None:
    reset_settings()
    set_settings_override(Settings(**_REQUIRED_ENV))  # type: ignore[arg-type]
    yield
    reset_settings()


def test_load_memory_node_does_not_write_user_memories_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "graph.nodes.fetch_user_memories",
        lambda _uid, **_kwargs: ["偏好简洁回答"],
    )
    monkeypatch.setattr("graph.nodes.load_thread_messages", lambda _tid: [])
    monkeypatch.setattr("graph.nodes.get_rolling_summary", lambda _tid: None)

    runtime = MagicMock()
    runtime.context = {"user_id": "u1", "role_id": "default", "tools": []}

    out = load_memory_node(
        {"messages": [HumanMessage(content="你好")]},
        runtime,
        {"configurable": {"thread_id": "thread-1"}},
    )

    assert out["user_memories"] == ["偏好简洁回答"]
    assert "user_memories_text" not in out


def test_load_memory_node_recovers_when_user_memory_read_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_memory_read(_uid: str, **_kwargs: object) -> list[str]:
        raise RuntimeError("embedding provider 500")

    monkeypatch.setattr("graph.nodes.fetch_user_memories", fail_memory_read)
    monkeypatch.setattr("graph.nodes.load_thread_messages", lambda _tid: [])
    monkeypatch.setattr("graph.nodes.get_rolling_summary", lambda _tid: None)

    runtime = MagicMock()
    runtime.context = {"user_id": "u1", "role_id": "default", "tools": []}

    out = load_memory_node(
        {"messages": [HumanMessage(content="你好")]},
        runtime,
        {"configurable": {"thread_id": "thread-1"}},
    )

    assert out["user_memories"] == []
    assert out["path_metrics"]["fallback_count"] == 1
    assert out["path_metrics"]["fallback_layer"] == "memory"
    assert out["path_metrics"]["fallback_reason"].startswith("RuntimeError:")
    assert out["path_metrics"]["fallback_action"] == "recoverable_error"
    assert out["path_metrics"]["fallback_recovered"] is True
