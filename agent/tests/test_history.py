"""Tests for memory.history — checkpoint message load and rolling summary."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any
from unittest.mock import MagicMock

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.base import CheckpointTuple
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.graph import END, START, MessagesState, StateGraph

from memory.checkpointer import get_checkpointer, reset_pooled_checkpointer
from memory.history import (
    ROLLING_SUMMARY_METADATA_KEY,
    ThreadIdError,
    count_turns,
    get_rolling_summary,
    load_thread_messages,
    set_history_checkpointer,
)
from settings.config import Settings, reset_settings

_REQUIRED = {
    "LANGSMITH_API_KEY": "lsv2_test",
    "OPENAI_API_KEY": "sk-test",
    "DATABASE_URL": "postgresql://postgres:test@localhost:5432/common_agent",
}


@pytest.fixture(autouse=True)
def _isolate_history(
    monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest
) -> Iterator[None]:
    reset_settings()
    reset_pooled_checkpointer()
    set_history_checkpointer(None)
    if request.node.get_closest_marker("integration") is None:
        for key in list(_REQUIRED) + list(Settings.model_fields):
            monkeypatch.delenv(key, raising=False)
        for key, value in _REQUIRED.items():
            monkeypatch.setenv(key, value)
    yield
    set_history_checkpointer(None)
    reset_pooled_checkpointer()
    reset_settings()


def _checkpoint_tuple(
    *,
    messages: list[Any] | None = None,
    metadata: dict[str, Any] | None = None,
    channel_summary: str | None = None,
) -> CheckpointTuple:
    channel_values: dict[str, Any] = {}
    if messages is not None:
        channel_values["messages"] = messages
    if channel_summary is not None:
        channel_values[ROLLING_SUMMARY_METADATA_KEY] = channel_summary

    checkpoint: dict[str, Any] = {
        "v": 4,
        "id": "chk-1",
        "ts": "2026-05-19T12:00:00+00:00",
        "channel_values": channel_values,
        "channel_versions": {},
        "versions_seen": {},
        "updated_channels": None,
    }
    return CheckpointTuple(
        config={"configurable": {"thread_id": "t-1"}},
        checkpoint=checkpoint,  # type: ignore[arg-type]
        metadata=metadata or {},
        parent_config=None,
        pending_writes=None,
    )


def test_load_thread_messages_empty_when_no_checkpoint() -> None:
    mock_cp = MagicMock(spec=PostgresSaver)
    mock_cp.get_tuple.return_value = None
    set_history_checkpointer(mock_cp)

    assert load_thread_messages("thread-a") == []
    mock_cp.get_tuple.assert_called_once_with(
        {"configurable": {"thread_id": "thread-a"}}
    )


def test_load_thread_messages_deserializes_dict_messages() -> None:
    mock_cp = MagicMock(spec=PostgresSaver)
    mock_cp.get_tuple.return_value = _checkpoint_tuple(
        messages=[
            {"type": "human", "data": {"content": "hi", "type": "human"}},
            {"type": "ai", "data": {"content": "hello", "type": "ai"}},
        ]
    )
    set_history_checkpointer(mock_cp)

    messages = load_thread_messages("thread-a")

    assert len(messages) == 2
    assert isinstance(messages[0], HumanMessage)
    assert messages[0].content == "hi"
    assert isinstance(messages[1], AIMessage)
    assert messages[1].content == "hello"


def test_get_rolling_summary_from_metadata() -> None:
    mock_cp = MagicMock(spec=PostgresSaver)
    mock_cp.get_tuple.return_value = _checkpoint_tuple(
        metadata={ROLLING_SUMMARY_METADATA_KEY: "User prefers bullet lists."}
    )
    set_history_checkpointer(mock_cp)

    assert get_rolling_summary("thread-a") == "User prefers bullet lists."


def test_get_rolling_summary_from_channel_values_fallback() -> None:
    mock_cp = MagicMock(spec=PostgresSaver)
    mock_cp.get_tuple.return_value = _checkpoint_tuple(channel_summary="Summary in channel")
    set_history_checkpointer(mock_cp)

    assert get_rolling_summary("thread-a") == "Summary in channel"


def test_get_rolling_summary_none_when_missing() -> None:
    mock_cp = MagicMock(spec=PostgresSaver)
    mock_cp.get_tuple.return_value = _checkpoint_tuple()
    set_history_checkpointer(mock_cp)

    assert get_rolling_summary("thread-a") is None


@pytest.mark.parametrize("bad_id", [None, "", "   "])
def test_blank_thread_id_raises(bad_id: str | None) -> None:
    with pytest.raises(ThreadIdError):
        load_thread_messages(bad_id)  # type: ignore[arg-type]
    with pytest.raises(ThreadIdError):
        get_rolling_summary(bad_id)  # type: ignore[arg-type]


def test_count_turns() -> None:
    messages = [
        HumanMessage(content="one"),
        AIMessage(content="a"),
        HumanMessage(content="two"),
        AIMessage(content="b"),
        AIMessage(content="extra ai"),
    ]
    assert count_turns(messages) == 2
    assert count_turns([]) == 0


def _postgres_reachable() -> bool:
    try:
        with get_checkpointer():
            return True
    except Exception:
        return False


@pytest.mark.integration
def test_integration_load_messages_and_summary() -> None:
    if not _postgres_reachable():
        pytest.skip("Postgres not reachable at DATABASE_URL")

    thread_id = "test-history-thread"
    config = {"configurable": {"thread_id": thread_id}}

    with get_checkpointer() as checkpointer:
        builder = StateGraph(MessagesState)
        builder.add_node("echo", lambda state: state)
        builder.add_edge(START, "echo")
        builder.add_edge("echo", END)
        graph = builder.compile(checkpointer=checkpointer)

        graph.invoke({"messages": [HumanMessage(content="turn 1")]}, config)
        graph.invoke({"messages": [HumanMessage(content="turn 2")]}, config)

        tpl = checkpointer.get_tuple(config)
        assert tpl is not None
        enriched_metadata = {
            **tpl.metadata,
            ROLLING_SUMMARY_METADATA_KEY: "Discussed two turns.",
        }
        checkpointer.put(
            tpl.config,
            tpl.checkpoint,
            enriched_metadata,  # type: ignore[arg-type]
            tpl.checkpoint["channel_versions"],
        )

        set_history_checkpointer(checkpointer)

        messages = load_thread_messages(thread_id)
        assert len(messages) >= 2
        assert count_turns(messages) >= 2
        assert any(getattr(m, "content", None) == "turn 1" for m in messages)
        assert any(getattr(m, "content", None) == "turn 2" for m in messages)

        summary = get_rolling_summary(thread_id)
        assert summary == "Discussed two turns."
