"""Tests for memory.mem0_write — mem0 infer=True post-turn storage."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from memory.mem0_client import build_mem0_config
from memory.mem0_write import (
    extract_and_store,
    reset_mem0_write_overrides,
    set_mem0_add_fn,
    turn_messages_to_mem0_payload,
)
from settings.config import Settings, reset_settings, set_settings_override

_REQUIRED_ENV = {
    "LANGSMITH_API_KEY": "lsv2_test",
    "OPENAI_API_KEY": "sk-test",
    "DATABASE_URL": "postgresql://postgres:test@localhost:5432/common_agent",
}


@pytest.fixture(autouse=True)
def _clean_mem0_write() -> None:
    reset_mem0_write_overrides()
    reset_settings()
    yield
    reset_mem0_write_overrides()
    reset_settings()


def test_turn_messages_to_mem0_payload_roles() -> None:
    turn = [
        HumanMessage(content="我叫刘日兴"),
        AIMessage(content="你好，刘日兴！"),
    ]
    payload = turn_messages_to_mem0_payload(turn)
    assert payload == [
        {"role": "user", "content": "我叫刘日兴"},
        {"role": "assistant", "content": "你好，刘日兴！"},
    ]


def test_extract_and_store_calls_add_with_raw_turn_and_infer_true() -> None:
    set_settings_override(Settings(**{**_REQUIRED_ENV, "MEM0_MOCK": False}))  # type: ignore[arg-type]

    add_mock = MagicMock(
        return_value={"results": [{"memory": "用户名叫刘日兴", "event": "ADD"}]}
    )
    set_mem0_add_fn(add_mock)

    turn = [
        HumanMessage(content="我是素食主义者"),
        AIMessage(content="已记录您的饮食偏好。"),
    ]
    stored = extract_and_store("user-99", turn)

    assert stored == ["用户名叫刘日兴"]
    add_mock.assert_called_once()
    payload, kwargs = add_mock.call_args
    assert kwargs["user_id"] == "user-99"
    assert kwargs.get("infer") is True
    messages = payload[0]
    assert len(messages) == 2
    assert messages[0] == {"role": "user", "content": "我是素食主义者"}
    assert messages[1] == {"role": "assistant", "content": "已记录您的饮食偏好。"}
    for item in messages:
        assert "User preference facts" not in item["content"]


def test_extract_and_store_skips_when_mem0_mock() -> None:
    set_settings_override(Settings(**{**_REQUIRED_ENV, "MEM0_MOCK": True}))  # type: ignore[arg-type]
    add_mock = MagicMock()
    set_mem0_add_fn(add_mock)

    stored = extract_and_store(
        "user-1",
        [HumanMessage(content="hello")],
    )

    assert stored == []
    add_mock.assert_not_called()


def test_build_mem0_config_includes_custom_instructions() -> None:
    config = build_mem0_config(Settings(**_REQUIRED_ENV))  # type: ignore[arg-type]
    instructions = config.get("custom_instructions", "")
    assert "stable preferences" in instructions.lower()
    assert "user messages" in instructions.lower()
