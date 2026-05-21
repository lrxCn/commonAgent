"""Tests for memory.mem0_client — local mem0 read (mocked; no live Qdrant)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from memory.mem0_client import (
    Mem0UserIdError,
    afetch_user_memories,
    fetch_user_memories,
    format_mem0_for_system,
    parse_memories_from_get_all,
    reset_mem0_memory,
    set_memory_factory,
)
from settings.config import Settings, reset_settings, set_settings_override

_REQUIRED_ENV = {
    "LANGSMITH_API_KEY": "lsv2_test",
    "OPENAI_API_KEY": "sk-test",
    "DATABASE_URL": "postgresql://postgres:test@localhost:5432/common_agent",
}


@pytest.fixture(autouse=True)
def _clean_mem0_and_settings() -> None:
    reset_mem0_memory()
    reset_settings()
    yield
    reset_mem0_memory()
    reset_settings()


def _settings(**extra: object) -> Settings:
    return Settings(
        **{
            **_REQUIRED_ENV,
            "MEM0_LLM_MODEL_NAME": "Qwen/Qwen2.5-7B-Instruct",
            **extra,
        }
    )  # type: ignore[arg-type]


def test_parse_memories_from_get_all_results() -> None:
    raw = {
        "results": [
            {"id": "1", "memory": "Prefers vegetarian food"},
            {"id": "2", "memory": "Works in Shanghai"},
            {"memory": ""},
        ]
    }
    assert parse_memories_from_get_all(raw) == [
        "Prefers vegetarian food",
        "Works in Shanghai",
    ]


def test_fetch_user_memories_with_mock_get_all(monkeypatch: pytest.MonkeyPatch) -> None:
    set_settings_override(_settings(MEM0_MOCK=False, MEM0_READ_LIMIT=10))
    mock_memory = MagicMock()
    mock_memory.get_all.return_value = {
        "results": [
            {"memory": "Likes concise answers"},
            {"memory": "Timezone is Asia/Shanghai"},
        ]
    }
    set_memory_factory(lambda: mock_memory)

    memories = fetch_user_memories("user-42")

    assert memories == ["Likes concise answers", "Timezone is Asia/Shanghai"]
    mock_memory.get_all.assert_called_once_with(
        filters={"user_id": "user-42"},
        top_k=10,
    )


def test_format_mem0_for_system_includes_bullets() -> None:
    text = format_mem0_for_system(["Fact A", "Fact B"])
    assert "- Fact A" in text
    assert "- Fact B" in text
    assert "## User preferences" in text


def test_format_mem0_for_system_empty() -> None:
    assert format_mem0_for_system([]) == ""


@pytest.mark.parametrize("bad_id", [None, "", "   "])
def test_fetch_user_memories_missing_user_id_raises(bad_id: str | None) -> None:
    set_settings_override(_settings(MEM0_MOCK=False))
    with pytest.raises(Mem0UserIdError):
        fetch_user_memories(bad_id)  # type: ignore[arg-type]


def test_fetch_user_memories_mock_mode_returns_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    set_settings_override(_settings(MEM0_MOCK=True))
    mock_memory = MagicMock()
    set_memory_factory(lambda: mock_memory)

    assert fetch_user_memories("user-1") == []
    mock_memory.get_all.assert_not_called()


@pytest.mark.anyio
async def test_afetch_user_memories() -> None:
    set_settings_override(_settings(MEM0_MOCK=False))
    mock_memory = MagicMock()
    mock_memory.get_all.return_value = {"results": [{"memory": "Async fact"}]}
    set_memory_factory(lambda: mock_memory)

    memories = await afetch_user_memories("user-async")

    assert memories == ["Async fact"]
