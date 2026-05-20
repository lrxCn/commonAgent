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
    "MEM0_MOCK": True,
}


@pytest.fixture(autouse=True)
def _settings() -> None:
    reset_settings()
    set_settings_override(Settings(**_REQUIRED_ENV))  # type: ignore[arg-type]
    yield
    reset_settings()


def test_load_memory_node_does_not_write_mem0_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "graph.nodes.fetch_user_memories",
        lambda _uid: ["偏好简洁回答"],
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

    assert out["mem0_memories"] == ["偏好简洁回答"]
    assert "mem0_text" not in out
