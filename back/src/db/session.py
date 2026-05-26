"""Engine and session factory for Back database access."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

_engine_cache: dict[str, Engine] = {}


def create_engine_from_url(database_url: str, *, echo: bool = False) -> Engine:
    connect_args: dict[str, object] = {}
    if database_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
    return create_engine(database_url, echo=echo, connect_args=connect_args)


def get_engine(database_url: str, *, echo: bool = False) -> Engine:
    if database_url not in _engine_cache:
        _engine_cache[database_url] = create_engine_from_url(database_url, echo=echo)
    return _engine_cache[database_url]


def clear_engine_cache() -> None:
    for engine in _engine_cache.values():
        engine.dispose()
    _engine_cache.clear()


def get_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)


@contextmanager
def session_scope(session_factory: sessionmaker[Session]) -> Iterator[Session]:
    session = session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
