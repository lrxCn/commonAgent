"""Tests for memory.summary_job — incremental rolling summary."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from memory.summary_job import (
    merge_summary_increment,
    select_new_middle_turns,
    set_summary_llm,
    update_rolling_summary,
)
from settings.config import Settings, reset_settings, set_settings_override

_REQUIRED_ENV = {
    "LANGSMITH_API_KEY": "lsv2_test",
    "OPENAI_API_KEY": "sk-test",
    "DATABASE_URL": "postgresql://postgres:test@localhost:5432/common_agent",
}


@pytest.fixture(autouse=True)
def _clean_summary_settings() -> None:
    set_summary_llm(None)
    reset_settings()
    yield
    set_summary_llm(None)
    reset_settings()


def _many_turn_messages(turn_count: int) -> list:
    messages = []
    for index in range(turn_count):
        messages.append(HumanMessage(content=f"human-{index}"))
        messages.append(AIMessage(content=f"ai-{index}"))
    return messages


def test_select_new_middle_turns_only_unsummarized_band() -> None:
    messages = _many_turn_messages(8)
    new_turns, new_through = select_new_middle_turns(
        messages,
        k=2,
        m=2,
        summarized_through=2,
    )
    assert len(new_turns) == 4
    assert new_through == 6
    assert new_turns[0][0].content == "human-2"


def test_select_new_middle_turns_empty_when_window_too_small() -> None:
    messages = _many_turn_messages(3)
    new_turns, new_through = select_new_middle_turns(
        messages,
        k=4,
        m=4,
        summarized_through=4,
    )
    assert new_turns == []
    assert new_through == 4


def test_merge_summary_increment_appends_content() -> None:
    set_summary_llm(
        lambda _prompt: "Earlier topics.\nUser asked about reimbursement policy."
    )
    merged = merge_summary_increment("Earlier topics.", "### Turn 3\n用户: 报销政策？")
    assert "reimbursement" in merged
    assert len(merged) > len("Earlier topics.")


def test_update_rolling_summary_persists_longer_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    set_settings_override(Settings(**_REQUIRED_ENV))  # type: ignore[arg-type]
    messages = _many_turn_messages(10)
    monkeypatch.setattr(
        "memory.summary_job.load_thread_messages",
        lambda _thread_id: messages,
    )
    monkeypatch.setattr(
        "memory.summary_job.get_rolling_summary_state",
        lambda _thread_id: ("Short.", 2),
    )

    saved: dict[str, object] = {}

    def _capture_save(thread_id: str, summary: str, *, through_turn: int) -> None:
        saved["thread_id"] = thread_id
        saved["summary"] = summary
        saved["through_turn"] = through_turn

    monkeypatch.setattr("memory.summary_job.save_rolling_summary", _capture_save)

    set_summary_llm(
        lambda _prompt: (
            "Short.\n"
            "Middle turns covered reimbursement, travel policy, and onboarding checklist items."
        )
    )

    result = update_rolling_summary("thread-sum-1", [], k=2, m=2)

    assert result is not None
    assert len(str(result)) > len("Short.")
    assert saved["through_turn"] == 8
    assert "reimbursement" in str(saved["summary"])


def test_update_rolling_summary_skips_when_no_middle_turns(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    set_settings_override(Settings(**_REQUIRED_ENV))  # type: ignore[arg-type]
    messages = _many_turn_messages(2)
    monkeypatch.setattr(
        "memory.summary_job.load_thread_messages",
        lambda _thread_id: messages,
    )
    monkeypatch.setattr(
        "memory.summary_job.get_rolling_summary_state",
        lambda _thread_id: ("Keep.", 2),
    )
    save_mock = MagicMock()
    monkeypatch.setattr("memory.summary_job.save_rolling_summary", save_mock)

    result = update_rolling_summary("thread-sum-2", [], k=2, m=2)

    assert result == "Keep."
    save_mock.assert_not_called()
