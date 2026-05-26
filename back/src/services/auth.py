"""Authenticate users and build /api/me payloads from the database."""

from __future__ import annotations

import bcrypt
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from db.models import Role, User, UserRole


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def authenticate_user(session: Session, username: str, password: str) -> User | None:
    user = session.scalar(
        select(User)
        .options(selectinload(User.roles).selectinload(UserRole.role))
        .where(User.username == username)
    )
    if user is None or not verify_password(password, user.password_hash):
        return None
    return user


def load_user_roles(session: Session, user_id: str) -> list[Role]:
    """Return roles for a user, deduplicated and in user_roles table order."""
    bindings = session.scalars(
        select(UserRole).where(UserRole.user_id == user_id)
    ).all()
    seen: set[str] = set()
    roles: list[Role] = []
    for binding in bindings:
        if binding.role_id in seen:
            continue
        seen.add(binding.role_id)
        role = session.get(Role, binding.role_id)
        if role is not None:
            roles.append(role)
    return roles


def build_me_payload(session: Session, user: User) -> dict[str, object]:
    roles = load_user_roles(session, user.user_id)
    return {
        "user_id": user.user_id,
        "username": user.username,
        "display_name": user.display_name,
        "is_admin": user.is_admin,
        "role_ids": [role.role_id for role in roles],
        "roles": [{"role_id": role.role_id, "name": role.name} for role in roles],
    }
