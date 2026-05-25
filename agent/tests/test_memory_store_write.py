"""Tests for LangGraph Store structured memory writes (task 71)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from langgraph.store.memory import InMemoryStore

from contracts.memory_store import profile_namespace
from intent.engine import classify_intent
from intent.signals import extract_signals
from memory.read import fetch_user_memories
from memory.store import reset_pooled_store, set_store_factory
from memory.structured_record import build_structured_memory_record, canonical_fact_text
from memory.write import (
    reset_write_overrides,
    set_store_put_fn,
    store_structured_record,
)
from settings.config import Settings, reset_settings, set_settings_override

_REQUIRED_ENV = {
    "LANGSMITH_API_KEY": "lsv2_test",
    "OPENAI_API_KEY": "sk-test",
    "DATABASE_URL": "postgresql://postgres:test@localhost:5432/common_agent",
}


@pytest.fixture(autouse=True)
def _clean_write_env() -> None:
    reset_write_overrides()
    reset_pooled_store()
    reset_settings()
    yield
    reset_write_overrides()
    reset_pooled_store()
    reset_settings()


def _settings(**extra: object) -> Settings:
    return Settings(
        **{
            **_REQUIRED_ENV,
            "MEM0_LLM_MODEL_NAME": "Qwen/Qwen2.5-7B-Instruct",
            **extra,
        }
    )  # type: ignore[arg-type]


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


def test_store_structured_record_puts_profile_payload_without_mem0_add() -> None:
    set_settings_override(
        _settings(MEMORY_STORE_MOCK=False, MEM0_MOCK=False, MEMORY_STORE_SETUP=False)
    )
    store = InMemoryStore()
    set_store_factory(lambda: store)
    record = _structured_record_for("我叫张三")
    canonical = canonical_fact_text(record)

    with patch("memory.write.attach_run_metadata") as attach_mock:
        result = store_structured_record("user-99", record)

    assert result.status == "stored"
    assert result.stored_count == 1
    assert list(result.stored_memories) == [canonical]
    item = store.get(profile_namespace("user-99"), "name")
    assert item is not None
    assert item.value["value"] == "张三"
    assert item.value["canonical"] == canonical
    assert item.value["source_turn_id"] == "thread-1:turn-1"

    metadata = attach_mock.call_args.args[0]
    assert metadata["memory_write.mode"] == "structured"
    assert metadata["memory_store.status"] == "stored"
    assert metadata["mem0_write.status"] == "stored"


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
        _settings(MEMORY_STORE_MOCK=False, MEM0_MOCK=False, MEMORY_STORE_SETUP=False)
    )
    store = InMemoryStore()
    set_store_factory(lambda: store)
    record = _structured_record_for(message)
    result = store_structured_record("user-seed", record)

    assert result.status == "stored"
    assert result.stored_count >= 1
    assert result.status != "stored_empty"


def test_store_structured_record_mock_mode_returns_predictable_stored_result() -> None:
    set_settings_override(_settings(MEMORY_STORE_MOCK=True))
    record = _structured_record_for("我叫张三")
    canonical = canonical_fact_text(record)
    put_mock = MagicMock()
    set_store_put_fn(put_mock)

    result = store_structured_record("user-1", record)

    assert result.status == "stored"
    assert result.stored_count == 1
    assert list(result.stored_memories) == [canonical]
    put_mock.assert_not_called()


def test_store_structured_record_returns_failed_reason_on_put_error() -> None:
    set_settings_override(
        _settings(MEMORY_STORE_MOCK=False, MEM0_MOCK=False, MEMORY_STORE_SETUP=False)
    )
    record = _structured_record_for("我叫张三")
    set_store_put_fn(MagicMock(side_effect=RuntimeError("store down")))

    with patch("memory.write.attach_run_metadata") as attach_mock:
        result = store_structured_record("user-1", record)

    assert result.status == "failed"
    assert result.reason == "RuntimeError"
    assert result.stored_count == 0
    metadata = attach_mock.call_args.args[0]
    assert metadata["memory_write.mode"] == "structured"
    assert metadata["memory_store.status"] == "failed"
    assert metadata["mem0_write.status"] == "failed"


def test_store_structured_record_is_readable_via_fetch_user_memories() -> None:
    set_settings_override(
        _settings(
            MEMORY_STORE_MOCK=False,
            MEM0_MOCK=False,
            MEMORY_READ_LIMIT=10,
            MEMORY_STORE_SETUP=False,
        )
    )
    store = InMemoryStore()
    set_store_factory(lambda: store)
    record = _structured_record_for("我叫张三")
    canonical = canonical_fact_text(record)

    store_structured_record("user-roundtrip", record)
    facts = fetch_user_memories("user-roundtrip", store=store)

    assert canonical in facts
