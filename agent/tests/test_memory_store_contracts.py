"""LangGraph Store memory contract tests (task 69)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from contracts.memory_store import (
    MEMORY_STORE_FACTS_SEGMENT,
    MEMORY_STORE_PROFILE_SEGMENT,
    ProfileMemoryValue,
    UserMemoryReadResult,
    facts_namespace,
    profile_namespace,
)


def test_profile_namespace_matches_store_convention() -> None:
    assert profile_namespace("user-42") == ("users", "user-42", "profile")
    assert profile_namespace("user-42")[2] == MEMORY_STORE_PROFILE_SEGMENT


def test_facts_namespace_matches_store_convention() -> None:
    assert facts_namespace("user-42") == ("users", "user-42", "facts")
    assert facts_namespace("user-42")[2] == MEMORY_STORE_FACTS_SEGMENT


def test_namespace_helpers_reject_blank_user_id() -> None:
    with pytest.raises(ValueError, match="user_id cannot be blank"):
        profile_namespace("   ")
    with pytest.raises(ValueError, match="user_id cannot be blank"):
        facts_namespace("")


def test_profile_memory_value_serializes_store_payload() -> None:
    value = ProfileMemoryValue(
        value="张三",
        raw_utterance="我叫张三",
        source_turn_id="thread-1:turn-3",
        extraction_method="slot_fill_v1",
        updated_at="2026-05-25T12:00:00+08:00",
    )

    payload = value.to_store_dict()

    assert payload == {
        "value": "张三",
        "raw_utterance": "我叫张三",
        "source_turn_id": "thread-1:turn-3",
        "extraction_method": "slot_fill_v1",
        "updated_at": "2026-05-25T12:00:00+08:00",
    }


def test_profile_memory_value_rejects_blank_fields() -> None:
    with pytest.raises(ValidationError):
        ProfileMemoryValue(
            value="",
            raw_utterance="我叫张三",
            source_turn_id="thread-1:turn-3",
            extraction_method="slot_fill_v1",
            updated_at="2026-05-25T12:00:00+08:00",
        )


def test_user_memory_read_result_exposes_legacy_fact_list() -> None:
    result = UserMemoryReadResult(
        facts=["用户叫张三", "用户出生于1997年"],
    )

    assert result.as_fact_list() == ["用户叫张三", "用户出生于1997年"]


def test_user_memory_read_result_rejects_blank_facts() -> None:
    with pytest.raises(ValidationError):
        UserMemoryReadResult(facts=["valid", "  "])
