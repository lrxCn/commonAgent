"""LangGraph Store factory for user long-term memory (Postgres + pgvector)."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Any

from langgraph.store.base import BaseStore
from langgraph.store.memory import InMemoryStore
from langgraph.store.postgres import PostgresStore
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from settings.config import Settings, get_settings

_pool: ConnectionPool | None = None
_pooled_store: BaseStore | None = None
_store_factory: Callable[[], BaseStore] | None = None


def _build_store_index_config(settings: Settings) -> dict[str, Any]:
    """Build pgvector index config aligned with ``EMBEDDING_MODEL_DIMS``."""
    from infrastructure.llm.gateway import LlmGateway

    gateway = LlmGateway(settings)

    def _embed(texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        return gateway.embed_documents(texts)

    return {
        "dims": settings.EMBEDDING_MODEL_DIMS,
        "embed": _embed,
        "fields": ["text"],
    }


def _create_pooled_postgres_store(settings: Settings, *, setup: bool) -> PostgresStore:
    global _pool
    if _pool is None:
        _pool = ConnectionPool(
            conninfo=settings.DATABASE_URL,
            kwargs={
                "autocommit": True,
                "prepare_threshold": 0,
                "row_factory": dict_row,
            },
        )
    store = PostgresStore(_pool, index=_build_store_index_config(settings))
    if setup and settings.MEMORY_STORE_SETUP:
        store.setup()
    return store


def set_store_factory(factory: Callable[[], BaseStore] | None) -> None:
    """Replace Store construction for tests; pass None to clear."""
    global _store_factory, _pooled_store
    _store_factory = factory
    _pooled_store = None


@contextmanager
def get_store(*, setup: bool | None = None) -> Iterator[BaseStore]:
    """Yield a short-lived Store (Postgres or InMemory mock)."""
    settings = get_settings()
    if settings.MEMORY_STORE_MOCK:
        yield InMemoryStore()
        return

    should_setup = settings.MEMORY_STORE_SETUP if setup is None else setup
    with PostgresStore.from_conn_string(
        settings.DATABASE_URL,
        index=_build_store_index_config(settings),
    ) as store:
        if should_setup:
            store.setup()
        yield store


def get_pooled_store(*, setup: bool | None = None) -> BaseStore:
    """Return a shared Store for read-heavy graph paths."""
    global _pooled_store
    if _store_factory is not None:
        return _store_factory()

    settings = get_settings()
    if settings.MEMORY_STORE_MOCK:
        if _pooled_store is None:
            _pooled_store = InMemoryStore()
        return _pooled_store

    should_setup = settings.MEMORY_STORE_SETUP if setup is None else setup
    if _pooled_store is None:
        _pooled_store = _create_pooled_postgres_store(settings, setup=should_setup)
    elif should_setup and settings.MEMORY_STORE_SETUP:
        pooled = _pooled_store
        if isinstance(pooled, PostgresStore):
            pooled.setup()
    return _pooled_store


def reset_pooled_store() -> None:
    """Close the shared pool and clear cached store (for tests)."""
    global _pool, _pooled_store, _store_factory
    if _pool is not None:
        _pool.close()
    _pool = None
    _pooled_store = None
    _store_factory = None
