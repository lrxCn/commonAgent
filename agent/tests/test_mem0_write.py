"""Tests for memory.mem0_write — extractive local mem0 storage."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from memory.mem0_write import (
    build_mem0_add_payload,
    extract_and_store,
    extract_facts_from_turn,
    format_turn_transcript,
    reset_mem0_write_overrides,
    set_mem0_add_fn,
    set_mem0_extract_llm,
)
from settings.config import Settings, reset_settings, set_settings_override

_REQUIRED_ENV = {
    "LANGSMITH_API_KEY": "lsv2_test",
    "OPENAI_API_KEY": "sk-test",
    "DATABASE_URL": "postgresql://postgres:test@localhost:5432/common_agent",
}

_LONG_TRANSCRIPT = "\n".join(
    f"用户: 历史消息片段 {index}\n助手: 很长的回复 " * 20
    for index in range(30)
)


@pytest.fixture(autouse=True)
def _clean_mem0_write() -> None:
    reset_mem0_write_overrides()
    reset_settings()
    yield
    reset_mem0_write_overrides()
    reset_settings()


def test_format_turn_transcript_only_current_turn() -> None:
    turn = [
        HumanMessage(content="我喜欢简洁回答"),
        AIMessage(content="好的，我会简短回复。"),
    ]
    text = format_turn_transcript(turn)
    assert "简洁" in text
    assert "历史消息片段" not in text


def test_extract_facts_from_turn_parses_bullets() -> None:
    set_mem0_extract_llm(
        lambda _prompt: "- Prefers concise answers\n- Works in Shanghai"
    )
    facts = extract_facts_from_turn(
        [HumanMessage(content="我在上海，喜欢简洁回答")],
    )
    assert facts == ["Prefers concise answers", "Works in Shanghai"]


def test_build_mem0_add_payload_is_not_full_transcript() -> None:
    payload = build_mem0_add_payload(["Likes bullet lists"])
    assert len(payload) == 1
    content = payload[0]["content"]
    assert "Likes bullet lists" in content
    assert len(content) < len(_LONG_TRANSCRIPT)


def test_extract_and_store_calls_add_with_short_payload() -> None:
    set_settings_override(Settings(**{**_REQUIRED_ENV, "MEM0_MOCK": False}))  # type: ignore[arg-type]
    set_mem0_extract_llm(lambda _prompt: "- Prefers vegetarian food")

    add_mock = MagicMock()
    set_mem0_add_fn(add_mock)

    turn = [
        HumanMessage(content="我是素食主义者"),
        AIMessage(content="已记录您的饮食偏好。"),
    ]
    facts = extract_and_store("user-99", turn)

    assert facts == ["Prefers vegetarian food"]
    add_mock.assert_called_once()
    payload, kwargs = add_mock.call_args
    assert kwargs["user_id"] == "user-99"
    assert kwargs.get("infer") is False
    stored_content = payload[0][0]["content"]
    assert "vegetarian" in stored_content
    assert len(stored_content) < len(_LONG_TRANSCRIPT)
    assert "已记录您的饮食偏好" not in stored_content


def test_extract_and_store_skips_when_mem0_mock() -> None:
    set_settings_override(Settings(**{**_REQUIRED_ENV, "MEM0_MOCK": True}))  # type: ignore[arg-type]
    add_mock = MagicMock()
    set_mem0_add_fn(add_mock)

    facts = extract_and_store(
        "user-1",
        [HumanMessage(content="hello")],
    )

    assert facts == []
    add_mock.assert_not_called()
