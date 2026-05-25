"""Tests for LangGraph Store user memory read path (task 70)."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from langgraph.store.memory import InMemoryStore

from contracts.memory_store import facts_namespace, profile_namespace
from memory.checkpointer import get_checkpointer
from memory.read import (
    MemoryUserIdError,
    fetch_user_memories,
    profile_facts_to_strings,
    profile_value_to_canonical_fact,
    search_collection_facts,
)
from memory.store import reset_pooled_store, set_store_factory
from settings.config import Settings, reset_settings, set_settings_override

_REQUIRED_ENV = {
    "LANGSMITH_API_KEY": "lsv2_test",
    "OPENAI_API_KEY": "sk-test",
    "DATABASE_URL": "postgresql://postgres:test@localhost:5432/common_agent",
}


@pytest.fixture(autouse=True)
def _clean_store_settings(request: pytest.FixtureRequest) -> Iterator[None]:
    reset_pooled_store()
    reset_settings()
    if request.node.get_closest_marker("integration") is not None:
        yield
        reset_pooled_store()
        reset_settings()
        return
    yield
    reset_pooled_store()
    reset_settings()


def _postgres_reachable() -> bool:
    try:
        with get_checkpointer():
            return True
    except Exception:
        return False


def _settings(**extra: object) -> Settings:
    return Settings(
        **{
            **_REQUIRED_ENV,
            "MEMORY_EXTRACT_MODEL_NAME": "Qwen/Qwen2.5-7B-Instruct",
            **extra,
        }
    )  # type: ignore[arg-type]


def _seed_profile_and_collection(store: InMemoryStore, user_id: str) -> None:
    store.put(
        profile_namespace(user_id),
        "name",
        {
            "value": "张三",
            "raw_utterance": "我叫张三",
            "source_turn_id": "thread-1:turn-1",
            "extraction_method": "slot_fill_v1",
            "updated_at": "2026-05-25T00:00:00+00:00",
        },
    )
    store.put(
        facts_namespace(user_id),
        "fact-1",
        {"text": "用户偏好简洁回答"},
        index=["text"],
    )


def test_profile_value_to_canonical_fact_name() -> None:
    assert profile_value_to_canonical_fact("name", "张三") == "用户的名字是张三"


def test_profile_facts_to_strings_orders_known_attributes() -> None:
    store = InMemoryStore()
    user_id = "user-profile"
    store.put(
        profile_namespace(user_id),
        "city",
        {
            "value": "上海",
            "raw_utterance": "我住在上海",
            "source_turn_id": "t1",
            "extraction_method": "slot_fill_v1",
            "updated_at": "2026-05-25T00:00:00+00:00",
        },
    )
    store.put(
        profile_namespace(user_id),
        "name",
        {
            "value": "张三",
            "raw_utterance": "我叫张三",
            "source_turn_id": "t1",
            "extraction_method": "slot_fill_v1",
            "updated_at": "2026-05-25T00:00:00+00:00",
        },
    )

    facts = profile_facts_to_strings(store, user_id, limit=10)

    assert facts == ["用户的名字是张三", "用户生活在上海"]


def test_fetch_user_memories_merges_profile_before_collection() -> None:
    set_settings_override(
        _settings(MEMORY_STORE_MOCK=False, MEMORY_READ_LIMIT=10)
    )
    store = InMemoryStore()
    _seed_profile_and_collection(store, "user-merge")
    set_store_factory(lambda: store)

    facts = fetch_user_memories("user-merge", query="简洁")

    assert facts[0] == "用户的名字是张三"
    assert "用户偏好简洁回答" in facts


def test_fetch_user_memories_mock_mode_returns_empty() -> None:
    store = InMemoryStore()
    _seed_profile_and_collection(store, "user-mock")
    set_store_factory(lambda: store)
    set_settings_override(_settings(MEMORY_STORE_MOCK=True))

    assert fetch_user_memories("user-mock") == []


def test_format_user_memories_for_system_includes_bullets() -> None:
    from memory.formatting import format_user_memories_for_system

    text = format_user_memories_for_system(["Fact A", "Fact B"])
    assert "Fact A" in text
    assert "Fact B" in text
    assert text.startswith("## User preferences")


def test_format_user_memories_for_system_empty() -> None:
    from memory.formatting import format_user_memories_for_system

    assert format_user_memories_for_system([]) == ""


def test_search_collection_facts_without_query_lists_entries() -> None:
    store = InMemoryStore()
    store.put(
        facts_namespace("user-collection"),
        "fact-a",
        {"text": "喜欢咖啡"},
    )

    facts = search_collection_facts(
        store,
        "user-collection",
        query=None,
        limit=5,
    )

    assert facts == ["喜欢咖啡"]


@pytest.mark.parametrize("bad_id", [None, "", "   "])
def test_fetch_user_memories_missing_user_id_raises(bad_id: str | None) -> None:
    set_settings_override(_settings(MEMORY_STORE_MOCK=False))
    with pytest.raises(MemoryUserIdError):
        fetch_user_memories(bad_id)  # type: ignore[arg-type]


@pytest.mark.integration
def test_fetch_user_memories_from_postgres_store() -> None:
    if not _postgres_reachable():
        pytest.skip("Postgres not reachable at DATABASE_URL")

    reset_pooled_store()
    facts = fetch_user_memories("integration-read-user", query="hello")

    assert isinstance(facts, list)
