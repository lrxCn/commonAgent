"""Freeze pre-refactor infer=True mem0 write behavior as a refactor baseline.

Task 63 documents the current fact_update post_turn path: Policy-approved turns
still call ``extract_and_store(..., infer=True)``. When mem0 infer returns no
memories (e.g. small-model extraction miss), the write ends in ``stored_empty``
even though the user already saw a Commit-style confirmation.

Task 65 adds ``store_structured_record`` as the target deterministic path that
must not reproduce ``stored_empty`` for PRD positive cases under mock.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from intent.engine import classify_intent
from intent.signals import extract_signals
from memory.mem0_write import (
    extract_and_store,
    reset_mem0_write_overrides,
    set_mem0_add_fn,
    store_structured_record,
)
from memory.structured_record import build_structured_memory_record, canonical_fact_text
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
def _clean_mem0_write() -> None:
    reset_mem0_write_overrides()
    reset_settings()
    yield
    reset_mem0_write_overrides()
    reset_settings()


def _enable_real_mem0_write() -> None:
    set_settings_override(
        Settings(
            **{
                **_REQUIRED_ENV,
                "MEM0_MOCK": False,
                "MEM0_LLM_MODEL_NAME": "Qwen/Qwen2.5-7B-Instruct",
            }
        )
    )  # type: ignore[arg-type]


@pytest.mark.parametrize(("user_text", "assistant_text"), _FACT_UPDATE_TURNS)
def test_current_infer_path_always_uses_infer_true(
    user_text: str,
    assistant_text: str,
) -> None:
    """Baseline: post_turn still delegates extraction to mem0 infer."""
    _enable_real_mem0_write()
    add_mock = MagicMock(return_value={"results": [{"memory": "stored", "event": "ADD"}]})
    set_mem0_add_fn(add_mock)

    turn = [
        HumanMessage(content=user_text),
        AIMessage(content=assistant_text),
    ]
    result = extract_and_store("user-fact-update", turn)

    assert result.status == "stored"
    add_mock.assert_called_once()
    _, kwargs = add_mock.call_args
    assert kwargs.get("infer") is True


@pytest.mark.parametrize(("user_text", "assistant_text"), _FACT_UPDATE_TURNS)
def test_current_infer_path_can_reproduce_stored_empty(
    user_text: str,
    assistant_text: str,
) -> None:
    """Baseline bug: infer miss yields stored_empty after Commit-style reply."""
    _enable_real_mem0_write()
    set_mem0_add_fn(MagicMock(return_value={"results": []}))

    turn = [
        HumanMessage(content=user_text),
        AIMessage(content=assistant_text),
    ]
    result = extract_and_store("user-fact-update", turn)

    assert result.status == "stored_empty"
    assert result.stored_count == 0


def test_current_infer_path_stored_empty_is_distinct_from_skipped_mock() -> None:
    """Document status vocabulary used by post_turn logging today."""
    _enable_real_mem0_write()
    set_mem0_add_fn(MagicMock(return_value={"results": []}))

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
    """Target path: structured infer=False write stores canonical fact under mock."""
    _enable_real_mem0_write()
    signals = extract_signals(user_text)
    decision = classify_intent(user_text)
    record = build_structured_memory_record(
        signals,
        decision,
        source_turn_id="thread-target:turn-1",
    )
    assert record is not None

    canonical = canonical_fact_text(record)
    add_mock = MagicMock(
        return_value={"results": [{"memory": canonical, "event": "ADD"}]}
    )
    set_mem0_add_fn(add_mock)

    result = store_structured_record("user-fact-update", record)

    assert result.status == "stored"
    assert result.stored_count >= 1
    assert result.status != "stored_empty"
    _, kwargs = add_mock.call_args
    assert kwargs.get("infer") is False
