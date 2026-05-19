"""Postgres checkpointer factory for LangGraph (thread_id session key)."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from langgraph.checkpoint.postgres import PostgresSaver
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from settings.config import get_settings

_pool: ConnectionPool | None = None
_pooled_saver: PostgresSaver | None = None


@contextmanager
def get_checkpointer(*, setup: bool = True) -> Iterator[PostgresSaver]:
    """Yield a PostgresSaver using ``DATABASE_URL`` (short-lived connection).

    Prefer this in tests and one-off scripts. For a process-wide saver used when
    compiling graphs at import time, use :func:`get_pooled_checkpointer`.
    """
    settings = get_settings()
    with PostgresSaver.from_conn_string(settings.DATABASE_URL) as checkpointer:
        if setup:
            checkpointer.setup()
        yield checkpointer


def get_pooled_checkpointer(*, setup: bool = True) -> PostgresSaver:
    """Return a shared PostgresSaver backed by a connection pool.

    Suitable for ``graph.compile(checkpointer=...)`` in long-running services.
    Call :func:`reset_pooled_checkpointer` in tests to tear down the pool.
    """
    global _pool, _pooled_saver
    if _pooled_saver is None:
        settings = get_settings()
        _pool = ConnectionPool(
            conninfo=settings.DATABASE_URL,
            kwargs={
                "autocommit": True,
                "prepare_threshold": 0,
                "row_factory": dict_row,
            },
        )
        _pooled_saver = PostgresSaver(_pool)
        if setup:
            _pooled_saver.setup()
    return _pooled_saver


def reset_pooled_checkpointer() -> None:
    """Close the shared pool and clear the cached saver (for tests)."""
    global _pool, _pooled_saver
    if _pool is not None:
        _pool.close()
    _pool = None
    _pooled_saver = None
