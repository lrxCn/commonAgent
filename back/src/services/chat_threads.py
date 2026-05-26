"""Chat thread ownership checks and first-chat registration."""

from __future__ import annotations

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from api.errors import forbidden
from db.models import ChatThread


def verify_thread_access(session: Session, *, user_id: str, thread_id: str) -> None:
    """Reject when ``thread_id`` belongs to another user (read paths; no registration)."""
    existing = session.get(ChatThread, thread_id)
    if existing is not None and existing.user_id != user_id:
        raise forbidden("无权访问该会话")


def ensure_thread_access(session: Session, *, user_id: str, thread_id: str) -> None:
    """Register a new thread for ``user_id`` or verify existing ownership."""
    existing = session.get(ChatThread, thread_id)
    if existing is not None:
        if existing.user_id != user_id:
            raise forbidden("无权访问该会话")
        return

    session.add(ChatThread(thread_id=thread_id, user_id=user_id))
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        existing = session.get(ChatThread, thread_id)
        if existing is None or existing.user_id != user_id:
            raise forbidden("无权访问该会话") from None
