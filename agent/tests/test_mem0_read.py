"""Tests for memory.mem0_client — local mem0 read (mocked; no live Qdrant)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from langgraph.store.memory import InMemoryStore

from contracts.memory_store import profile_namespace
from memory.mem0_client import (
    Mem0UserIdError,
    _apply_mem0_openai_timeout,
    afetch_user_memories,
    fetch_user_memories,
    format_mem0_for_system,
    parse_memories_from_get_all,
    reset_mem0_memory,
    set_memory_factory,
)
from memory.store import reset_pooled_store, set_store_factory
from settings.config import Settings, reset_settings, set_settings_override

_REQUIRED_ENV = {
    "LANGSMITH_API_KEY": "lsv2_test",
    "OPENAI_API_KEY": "sk-test",
    "DATABASE_URL": "postgresql://postgres:test@localhost:5432/common_agent",
}


@pytest.fixture(autouse=True)
def _clean_mem0_and_settings() -> None:
    reset_mem0_memory()
    reset_pooled_store()
    reset_settings()
    yield
    reset_mem0_memory()
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


def test_apply_mem0_openai_timeout_replaces_llm_client() -> None:
    settings = _settings(MEM0_LLM_TIMEOUT_SECONDS=4.5)
    memory = MagicMock()
    memory.llm.client = object()

    _apply_mem0_openai_timeout(memory, settings)

    assert memory.llm.client.timeout == 4.5
    assert str(memory.llm.client.base_url) == f"{settings.OPENAI_BASE_URL}/"


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


def test_fetch_user_memories_with_store_profile(monkeypatch: pytest.MonkeyPatch) -> None:
    set_settings_override(
        _settings(MEM0_MOCK=False, MEMORY_STORE_MOCK=False, MEMORY_READ_LIMIT=10)
    )
    store = InMemoryStore()
    store.put(
        profile_namespace("user-42"),
        "name",
        {
            "value": "Likes concise answers",
            "raw_utterance": "Likes concise answers",
            "source_turn_id": "t1",
            "extraction_method": "slot_fill_v1",
            "updated_at": "2026-05-25T00:00:00+00:00",
        },
    )
    set_store_factory(lambda: store)

    memories = fetch_user_memories("user-42")

    assert len(memories) == 1
    assert "Likes concise answers" in memories[0]


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
    set_settings_override(_settings(MEMORY_STORE_MOCK=True))
    store = InMemoryStore()
    set_store_factory(lambda: store)

    assert fetch_user_memories("user-1") == []


@pytest.mark.anyio
async def test_afetch_user_memories() -> None:
    set_settings_override(_settings(MEMORY_STORE_MOCK=False, MEM0_MOCK=False))
    store = InMemoryStore()
    store.put(
        profile_namespace("user-async"),
        "name",
        {
            "value": "Async fact",
            "raw_utterance": "Async fact",
            "source_turn_id": "t1",
            "extraction_method": "slot_fill_v1",
            "updated_at": "2026-05-25T00:00:00+00:00",
        },
    )
    set_store_factory(lambda: store)

    memories = await afetch_user_memories("user-async")

    assert len(memories) == 1
    assert "Async fact" in memories[0]
