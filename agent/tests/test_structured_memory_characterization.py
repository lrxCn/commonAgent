"""Freeze langmem inferred write behavior after mem0 removal (task 73+)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from intent.engine import classify_intent
from intent.signals import extract_signals
from langgraph.store.memory import InMemoryStore
from memory.store import reset_pooled_store, set_store_factory
from memory.structured_record import build_structured_memory_record
from memory.write import (
    extract_and_store,
    reset_write_overrides,
    set_manager_invoke_fn,
    store_structured_record,
)
from settings.config import Settings, reset_settings, set_settings_override

_REQUIRED_ENV = {
    "LANGSMITH_API_KEY": "lsv2_test",
    "OPENAI_API_KEY": "sk-test",
    "DATABASE_URL": "postgresql://postgres:test@localhost:5432/common_agent",
}

_FACT_UPDATE_TURNS: tuple[tuple[str, str], ...] = (
    ("我叫张三", "已收到，我会把这个信息作为你的偏好/事实参考。"),
    ("我出生于1997年", "已收到，我会把这个信息作为你的偏好/事实参考。"),
    ("我公司在天翔街188号", "已收到，我会把这个信息作为你的偏好/事实参考。"),
)


@pytest.fixture(autouse=True)
def _clean_memory_write() -> None:
    reset_write_overrides()
    reset_pooled_store()
    reset_settings()
    yield
    reset_write_overrides()
    reset_pooled_store()
    reset_settings()


def _enable_real_inferred_write() -> None:
    set_settings_override(
        Settings(
            **{
                **_REQUIRED_ENV,
                "MEMORY_STORE_MOCK": False,
                "MEMORY_EXTRACT_MODEL_NAME": "Qwen/Qwen2.5-7B-Instruct",
            }
        )
    )  # type: ignore[arg-type]


@pytest.mark.parametrize(("user_text", "assistant_text"), _FACT_UPDATE_TURNS)
def test_inferred_path_invokes_langmem_manager(
    user_text: str,
    assistant_text: str,
) -> None:
    _enable_real_inferred_write()
    invoke_mock = MagicMock(
        return_value=[
            {
                "namespace": ("users", "user-fact-update", "facts"),
                "key": "fact-1",
                "value": {"kind": "Memory", "content": {"content": "stored"}},
            }
        ]
    )
    set_manager_invoke_fn(invoke_mock)

    turn = [
        HumanMessage(content=user_text),
        AIMessage(content=assistant_text),
    ]
    result = extract_and_store("user-fact-update", turn)

    assert result.status == "stored"
    invoke_mock.assert_called_once()


@pytest.mark.parametrize(("user_text", "assistant_text"), _FACT_UPDATE_TURNS)
def test_inferred_path_can_reproduce_stored_empty(
    user_text: str,
    assistant_text: str,
) -> None:
    _enable_real_inferred_write()
    set_manager_invoke_fn(MagicMock(return_value=[]))

    turn = [
        HumanMessage(content=user_text),
        AIMessage(content=assistant_text),
    ]
    result = extract_and_store("user-fact-update", turn)

    assert result.status == "stored_empty"
    assert result.stored_count == 0


def test_inferred_path_stored_empty_is_distinct_from_skipped_mock() -> None:
    _enable_real_inferred_write()
    set_manager_invoke_fn(MagicMock(return_value=[]))

    result = extract_and_store(
        "user-fact-update",
        [
            HumanMessage(content="我叫张三"),
            AIMessage(content="已收到，我会把这个信息作为你的偏好/事实参考。"),
        ],
    )

    assert result.status == "stored_empty"
    assert result.status != "skipped_mock"
    assert result.status != "stored"


@pytest.mark.parametrize("user_text", [text for text, _ in _FACT_UPDATE_TURNS])
def test_structured_store_target_path_does_not_return_stored_empty(user_text: str) -> None:
    set_settings_override(
        Settings(
            **{
                **_REQUIRED_ENV,
                "MEMORY_STORE_MOCK": False,
                "MEMORY_STORE_SETUP": False,
            }
        )
    )  # type: ignore[arg-type]
    store = InMemoryStore()
    set_store_factory(lambda: store)
    invoke_mock = MagicMock()
    set_manager_invoke_fn(invoke_mock)

    signals = extract_signals(user_text)
    decision = classify_intent(user_text)
    record = build_structured_memory_record(
        signals,
        decision,
        source_turn_id="thread-target:turn-1",
    )
    assert record is not None

    result = store_structured_record("user-fact-update", record)

    assert result.status == "stored"
    assert result.stored_count >= 1
    assert result.status != "stored_empty"
    invoke_mock.assert_not_called()
