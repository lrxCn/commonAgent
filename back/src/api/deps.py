"""FastAPI dependencies for database sessions and authenticated users."""

from __future__ import annotations

from collections.abc import Generator
from typing import Annotated

from fastapi import Depends, Header, Request
from sqlalchemy.orm import Session

from api.errors import forbidden, unauthorized
from auth.session_keys import SESSION_USER_ID
from db.models import User
from db.session import get_engine, get_session_factory
from settings.config import Settings, get_settings


def get_db_session(
    settings: Annotated[Settings, Depends(get_settings)],
) -> Generator[Session, None, None]:
    engine = get_engine(settings.DATABASE_URL)
    session_factory = get_session_factory(engine)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


def get_session_user_id(request: Request) -> str | None:
    user_id = request.session.get(SESSION_USER_ID)
    if not isinstance(user_id, str) or not user_id:
        return None
    return user_id


def require_current_user(
    request: Request,
    db: Annotated[Session, Depends(get_db_session)],
) -> User:
    user_id = get_session_user_id(request)
    if user_id is None:
        raise unauthorized()
    user = db.get(User, user_id)
    if user is None:
        request.session.clear()
        raise unauthorized()
    return user


def require_admin(
    user: Annotated[User, Depends(require_current_user)],
) -> User:
    if not user.is_admin:
        raise forbidden()
    return user


def require_internal_key(
    settings: Annotated[Settings, Depends(get_settings)],
    x_internal_key: Annotated[str | None, Header(alias="X-Internal-Key")] = None,
) -> None:
    expected = (settings.INTERNAL_API_KEY or "").strip()
    provided = (x_internal_key or "").strip()
    if not expected or provided != expected:
        raise unauthorized("内部接口未授权")
