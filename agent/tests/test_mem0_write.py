"""Tests for memory.mem0_write — mem0 infer=True post-turn storage."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from openai import APITimeoutError

from memory.mem0_write import (
    extract_and_store,
    reset_mem0_write_overrides,
    set_mem0_add_fn,
    store_structured_record,
    turn_messages_to_mem0_payload,
)
from memory.structured_record import build_structured_memory_record, canonical_fact_text
from intent.engine import classify_intent
from intent.signals import extract_signals
from memory.mem0_client import build_mem0_config
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
    set_settings_override(
        Settings(
            **{
                **_REQUIRED_ENV,
                "MEM0_MOCK": False,
                "MEM0_LLM_MODEL_NAME": "Qwen/Qwen2.5-7B-Instruct",
            }
        )
    )  # type: ignore[arg-type]

    add_mock = MagicMock(
        return_value={"results": [{"memory": "用户名叫刘日兴", "event": "ADD"}]}
    )
    set_mem0_add_fn(add_mock)

    turn = [
        HumanMessage(content="我是素食主义者"),
        AIMessage(content="已记录您的饮食偏好。"),
    ]
    stored = extract_and_store("user-99", turn)

    assert stored.status == "stored"
    assert list(stored.stored_memories) == ["用户名叫刘日兴"]
    assert stored.stored_count == 1
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
    set_settings_override(
        Settings(
            **{
                **_REQUIRED_ENV,
                "MEM0_MOCK": True,
                "MEM0_LLM_MODEL_NAME": "Qwen/Qwen2.5-7B-Instruct",
            }
        )
    )  # type: ignore[arg-type]
    add_mock = MagicMock()
    set_mem0_add_fn(add_mock)

    stored = extract_and_store(
        "user-1",
        [HumanMessage(content="hello")],
    )

    assert stored.status == "skipped_mock"
    add_mock.assert_not_called()


def test_build_mem0_config_includes_custom_instructions() -> None:
    config = build_mem0_config(
        Settings(
            **{
                **_REQUIRED_ENV,
                "MEM0_LLM_MODEL_NAME": "Qwen/Qwen2.5-7B-Instruct",
            }
        )
    )  # type: ignore[arg-type]
    instructions = config.get("custom_instructions", "")
    assert "stable preferences" in instructions.lower()
    assert "user messages" in instructions.lower()


def test_build_mem0_config_uses_dedicated_small_model() -> None:
    config = build_mem0_config(
        Settings(
            **{
                **_REQUIRED_ENV,
                "OPENAI_MODEL_NAME": "Pro/moonshotai/Kimi-K2.6",
                "MEM0_LLM_MODEL_NAME": "Qwen/Qwen2.5-7B-Instruct",
                "MEM0_LLM_MAX_TOKENS": 96,
                "MEM0_LLM_TIMEOUT_SECONDS": 4.5,
            }
        )
    )  # type: ignore[arg-type]

    llm = config["llm"]["config"]
    assert llm["model"] == "Qwen/Qwen2.5-7B-Instruct"
    assert llm["model"] != "Pro/moonshotai/Kimi-K2.6"
    assert llm["max_tokens"] == 96
    assert "timeout" not in llm


def test_extract_and_store_returns_failed_reason_on_timeout() -> None:
    set_settings_override(
        Settings(
            **{
                **_REQUIRED_ENV,
                "MEM0_MOCK": False,
                "MEM0_LLM_MODEL_NAME": "Qwen/Qwen2.5-7B-Instruct",
            }
        )
    )  # type: ignore[arg-type]
    request = MagicMock()
    set_mem0_add_fn(MagicMock(side_effect=APITimeoutError(request=request)))

    stored = extract_and_store("user-1", [HumanMessage(content="hello")])

    assert stored.status == "failed"
    assert stored.reason == "APITimeoutError"
    assert stored.stored_count == 0


def test_extract_and_store_returns_failed_reason_on_add_error() -> None:
    set_settings_override(
        Settings(
            **{
                **_REQUIRED_ENV,
                "MEM0_MOCK": False,
                "MEM0_LLM_MODEL_NAME": "Qwen/Qwen2.5-7B-Instruct",
            }
        )
    )  # type: ignore[arg-type]
    set_mem0_add_fn(MagicMock(side_effect=RuntimeError("mem0 down")))

    stored = extract_and_store("user-1", [HumanMessage(content="hello")])

    assert stored.status == "failed"
    assert stored.reason == "RuntimeError"
    assert stored.stored_count == 0


def _structured_record_for(message: str, *, source_turn_id: str = "thread-1:turn-1"):
    signals = extract_signals(message)
    decision = classify_intent(message)
    record = build_structured_memory_record(
        signals,
        decision,
        source_turn_id=source_turn_id,
    )
    assert record is not None
    return record


def test_store_structured_record_calls_add_with_canonical_fact_and_infer_false() -> None:
    set_settings_override(
        Settings(
            **{
                **_REQUIRED_ENV,
                "MEM0_MOCK": False,
                "MEM0_LLM_MODEL_NAME": "Qwen/Qwen2.5-7B-Instruct",
            }
        )
    )  # type: ignore[arg-type]

    record = _structured_record_for("我叫张三")
    canonical = canonical_fact_text(record)
    add_mock = MagicMock(
        return_value={"results": [{"memory": canonical, "event": "ADD"}]}
    )
    set_mem0_add_fn(add_mock)

    with patch("memory.mem0_write.attach_run_metadata") as attach_mock:
        result = store_structured_record("user-99", record)

    assert result.status == "stored"
    assert result.stored_count == 1
    assert list(result.stored_memories) == [canonical]
    add_mock.assert_called_once()
    payload, kwargs = add_mock.call_args
    assert payload[0] == canonical
    assert kwargs["user_id"] == "user-99"
    assert kwargs.get("infer") is False
    assert kwargs["metadata"]["attribute"] == "name"
    assert kwargs["metadata"]["source_turn_id"] == "thread-1:turn-1"

    metadata = attach_mock.call_args.args[0]
    assert metadata["memory_write.mode"] == "structured"
    assert metadata["memory_write.record.attribute"] == "name"
    assert metadata["mem0_write.status"] == "stored"
    assert metadata["mem0_write.stored_count"] == 1


@pytest.mark.parametrize(
    "message",
    [
        "我叫张三",
        "我出生于1997年",
        "我公司在天翔街188号",
    ],
)
def test_store_structured_record_seed_positive_cases_store_at_least_one(
    message: str,
) -> None:
    set_settings_override(
        Settings(
            **{
                **_REQUIRED_ENV,
                "MEM0_MOCK": False,
                "MEM0_LLM_MODEL_NAME": "Qwen/Qwen2.5-7B-Instruct",
            }
        )
    )  # type: ignore[arg-type]

    record = _structured_record_for(message)
    canonical = canonical_fact_text(record)
    set_mem0_add_fn(
        MagicMock(return_value={"results": [{"memory": canonical, "event": "ADD"}]})
    )

    result = store_structured_record("user-seed", record)

    assert result.status == "stored"
    assert result.stored_count >= 1
    assert result.status != "stored_empty"


def test_store_structured_record_mock_mode_returns_predictable_stored_result() -> None:
    set_settings_override(
        Settings(
            **{
                **_REQUIRED_ENV,
                "MEM0_MOCK": True,
                "MEM0_LLM_MODEL_NAME": "Qwen/Qwen2.5-7B-Instruct",
            }
        )
    )  # type: ignore[arg-type]

    record = _structured_record_for("我叫张三")
    canonical = canonical_fact_text(record)
    add_mock = MagicMock()
    set_mem0_add_fn(add_mock)

    result = store_structured_record("user-1", record)

    assert result.status == "stored"
    assert result.stored_count == 1
    assert list(result.stored_memories) == [canonical]
    add_mock.assert_not_called()


def test_store_structured_record_returns_failed_reason_on_add_error() -> None:
    set_settings_override(
        Settings(
            **{
                **_REQUIRED_ENV,
                "MEM0_MOCK": False,
                "MEM0_LLM_MODEL_NAME": "Qwen/Qwen2.5-7B-Instruct",
            }
        )
    )  # type: ignore[arg-type]

    record = _structured_record_for("我叫张三")
    set_mem0_add_fn(MagicMock(side_effect=RuntimeError("mem0 down")))

    with patch("memory.mem0_write.attach_run_metadata") as attach_mock:
        result = store_structured_record("user-1", record)

    assert result.status == "failed"
    assert result.reason == "RuntimeError"
    assert result.stored_count == 0
    metadata = attach_mock.call_args.args[0]
    assert metadata["memory_write.mode"] == "structured"
    assert metadata["mem0_write.status"] == "failed"
