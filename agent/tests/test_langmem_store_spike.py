"""Dependency spike: Postgres Store setup coexists with checkpointer (task 69).

Store implementation ships inside ``langgraph-checkpoint-postgres>=3.1.0`` as
``langgraph.store.postgres`` — no separate ``langgraph-store-postgres`` package.

Semantic index setup requires pgvector (task 75); without the extension the
index smoke test is skipped.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

import pytest
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.store.postgres import PostgresStore
from psycopg import connect

from memory.checkpointer import get_checkpointer, reset_pooled_checkpointer
from settings.config import Settings, get_settings, reset_settings

_REQUIRED = {
    "LANGSMITH_API_KEY": "lsv2_test",
    "OPENAI_API_KEY": "sk-test",
    "DATABASE_URL": "postgresql://postgres:test@localhost:5432/common_agent",
}


@pytest.fixture(autouse=True)
def _isolate_settings(
    monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest
) -> Iterator[None]:
    reset_settings()
    reset_pooled_checkpointer()
    if request.node.get_closest_marker("integration") is not None:
        yield
        reset_pooled_checkpointer()
        reset_settings()
        return

    for key in list(_REQUIRED) + list(Settings.model_fields):
        monkeypatch.delenv(key, raising=False)
    for key, value in _REQUIRED.items():
        monkeypatch.setenv(key, value)
    yield
    reset_pooled_checkpointer()
    reset_settings()


def _postgres_reachable() -> bool:
    try:
        with get_checkpointer():
            return True
    except Exception:
        return False


def _pgvector_available() -> bool:
    settings = get_settings()
    try:
        with connect(settings.DATABASE_URL) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1 FROM pg_extension WHERE extname = 'vector'")
                return cur.fetchone() is not None
    except Exception:
        return False


@contextmanager
def _store_without_index() -> Iterator[PostgresStore]:
    settings = get_settings()
    with PostgresStore.from_conn_string(settings.DATABASE_URL) as store:
        store.setup()
        yield store


@pytest.mark.integration
def test_postgres_store_setup_coexists_with_checkpointer() -> None:
    """Store migrations and checkpoint tables can live in the same DATABASE_URL."""
    if not _postgres_reachable():
        pytest.skip("Postgres not reachable at DATABASE_URL")

    thread_id = "test-langmem-store-spike-checkpoint"
    config = {"configurable": {"thread_id": thread_id}}

    with get_checkpointer(setup=True) as checkpointer, _store_without_index() as store:
        builder = StateGraph(MessagesState)
        builder.add_node("echo", lambda state: state)
        builder.add_edge(START, "echo")
        builder.add_edge("echo", END)
        graph = builder.compile(checkpointer=checkpointer)

        graph.invoke(
            {"messages": [HumanMessage(content="store spike checkpoint roundtrip")]},
            config,
        )
        snapshot = graph.get_state(config)

        namespace = ("users", "spike-user", "profile")
        store.put(namespace, "name", {"value": "spike", "source": "task-69"})
        item = store.get(namespace, "name")

    assert snapshot is not None
    assert snapshot.values.get("messages")
    assert item is not None
    assert item.value["value"] == "spike"


@pytest.mark.integration
def test_postgres_store_semantic_index_requires_pgvector() -> None:
    """Collection semantic search needs pgvector; skip until task 75 enables it."""
    if not _postgres_reachable():
        pytest.skip("Postgres not reachable at DATABASE_URL")
    if not _pgvector_available():
        pytest.skip("pgvector extension not installed — complete task 75 first")

    settings = get_settings()

    def _fake_embed(texts: list[str]) -> list[list[float]]:
        return [[0.1] * 8 for _ in texts]

    with PostgresStore.from_conn_string(
        settings.DATABASE_URL,
        index={"dims": 8, "embed": _fake_embed, "fields": ["text"]},
    ) as store:
        store.setup()
