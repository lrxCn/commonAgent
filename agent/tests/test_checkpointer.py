"""Postgres checkpointer factory and persistence tests."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pytest
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.graph import END, START, MessagesState, StateGraph

from memory.checkpointer import (
    get_checkpointer,
    get_pooled_checkpointer,
    reset_pooled_checkpointer,
)
from settings.config import Settings, reset_settings

_REQUIRED = {
    "LANGSMITH_API_KEY": "lsv2_test",
    "OPENAI_API_KEY": "sk-test",
    "DATABASE_URL": "postgresql://postgres:test@localhost:5432/common_agent",
}


@pytest.fixture(autouse=True)
def _isolate_settings(
    monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest
) -> Iterator[None]:
    reset_settings()
    reset_pooled_checkpointer()
    if request.node.get_closest_marker("integration") is not None:
        # Use agent/.env (or existing env) for live Postgres.
        yield
        reset_pooled_checkpointer()
        reset_settings()
        return

    for key in list(_REQUIRED) + list(Settings.model_fields):
        monkeypatch.delenv(key, raising=False)
    for key, value in _REQUIRED.items():
        monkeypatch.setenv(key, value)
    yield
    reset_pooled_checkpointer()
    reset_settings()


@contextmanager
def _fake_from_conn_string(mock_saver: MagicMock) -> Iterator[MagicMock]:
    yield mock_saver


def _postgres_reachable() -> bool:
    try:
        with get_checkpointer():
            return True
    except Exception:
        return False


def test_get_checkpointer_uses_database_url_from_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_saver = MagicMock(spec=PostgresSaver)
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://postgres:secret@dbhost:5432/common_agent",
    )
    reset_settings()

    with patch(
        "memory.checkpointer.PostgresSaver.from_conn_string",
        return_value=_fake_from_conn_string(mock_saver),
    ) as from_conn:
        with get_checkpointer() as checkpointer:
            assert checkpointer is mock_saver

    from_conn.assert_called_once_with(
        "postgresql://postgres:secret@dbhost:5432/common_agent"
    )
    mock_saver.setup.assert_called_once()


def test_get_checkpointer_skips_setup_when_disabled() -> None:
    mock_saver = MagicMock(spec=PostgresSaver)
    with patch(
        "memory.checkpointer.PostgresSaver.from_conn_string",
        return_value=_fake_from_conn_string(mock_saver),
    ):
        with get_checkpointer(setup=False) as checkpointer:
            assert checkpointer is mock_saver

    mock_saver.setup.assert_not_called()


def test_get_pooled_checkpointer_returns_singleton() -> None:
    mock_saver = MagicMock(spec=PostgresSaver)
    with patch("memory.checkpointer.ConnectionPool"), patch(
        "memory.checkpointer.PostgresSaver", return_value=mock_saver
    ):
        first = get_pooled_checkpointer(setup=True)
        second = get_pooled_checkpointer(setup=False)
        assert first is second
        mock_saver.setup.assert_called_once()


@pytest.mark.integration
def test_thread_checkpoint_roundtrip() -> None:
    if not _postgres_reachable():
        pytest.skip("Postgres not reachable at DATABASE_URL")

    thread_id = "test-checkpointer-thread"
    config = {"configurable": {"thread_id": thread_id}}

    with get_checkpointer() as checkpointer:
        builder = StateGraph(MessagesState)
        builder.add_node("echo", lambda state: state)
        builder.add_edge(START, "echo")
        builder.add_edge("echo", END)
        graph = builder.compile(checkpointer=checkpointer)

        graph.invoke(
            {"messages": [HumanMessage(content="hello checkpoint")]},
            config,
        )
        snapshot = graph.get_state(config)

    assert snapshot is not None
    assert snapshot.values.get("messages")
    assert any(
        getattr(m, "content", None) == "hello checkpoint"
        for m in snapshot.values["messages"]
    )
