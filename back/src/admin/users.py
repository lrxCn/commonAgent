"""User CRUD service for admin API."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from api.errors import conflict, forbidden, not_found
from db.models import Role, User, UserRole
from services.auth import hash_password, load_user_roles

ADMIN_SEED_USER_ID = "u-admin"
ADMIN_SEED_ROLE_ID = "role-admin"


def _new_user_id() -> str:
    return f"u-{uuid.uuid4().hex[:12]}"


def user_to_dict(db: Session, user: User) -> dict[str, object]:
    roles = load_user_roles(db, user.user_id)
    return {
        "user_id": user.user_id,
        "username": user.username,
        "display_name": user.display_name,
        "is_admin": user.is_admin,
        "role_ids": [role.role_id for role in roles],
        "roles": [{"role_id": role.role_id, "name": role.name} for role in roles],
        "created_at": user.created_at,
        "updated_at": user.updated_at,
    }


def _validate_role_ids(db: Session, role_ids: list[str]) -> list[str]:
    if not role_ids:
        raise conflict("至少选择一个角色", field_errors={"role_ids": "不能为空"})

    normalized: list[str] = []
    seen: set[str] = set()
    for raw in role_ids:
        role_id = raw.strip()
        if not role_id or role_id in seen:
            continue
        seen.add(role_id)
        if db.get(Role, role_id) is None:
            raise conflict(
                f"角色不存在：{role_id}",
                field_errors={"role_ids": f"未知角色 {role_id}"},
            )
        normalized.append(role_id)

    if not normalized:
        raise conflict("至少选择一个角色", field_errors={"role_ids": "不能为空"})
    return normalized


def _assert_admin_constraints(user: User, *, role_ids: list[str], is_admin: bool) -> None:
    if user.user_id != ADMIN_SEED_USER_ID:
        return
    if ADMIN_SEED_ROLE_ID not in role_ids:
        raise conflict(
            "admin 用户必须绑定 role-admin",
            field_errors={"role_ids": "需包含 role-admin"},
        )
    if not is_admin:
        raise forbidden("不可取消 admin 用户的管理员标记")


def list_users(db: Session) -> list[dict[str, object]]:
    users = db.scalars(
        select(User).order_by(User.username.asc())
    ).all()
    return [user_to_dict(db, user) for user in users]


def get_user(db: Session, user_id: str) -> dict[str, object]:
    user = db.get(User, user_id)
    if user is None:
        raise not_found("用户不存在")
    return user_to_dict(db, user)


def create_user(
    db: Session,
    *,
    username: str,
    password: str,
    display_name: str,
    role_ids: list[str],
) -> dict[str, object]:
    normalized_roles = _validate_role_ids(db, role_ids)
    is_admin = ADMIN_SEED_ROLE_ID in normalized_roles
    user = User(
        user_id=_new_user_id(),
        username=username.strip(),
        display_name=display_name.strip(),
        is_admin=is_admin,
        password_hash=hash_password(password),
    )
    db.add(user)
    db.flush()

    for role_id in normalized_roles:
        db.add(UserRole(user_id=user.user_id, role_id=role_id))

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise conflict("用户名已存在", field_errors={"username": "已占用"}) from exc
    db.refresh(user)
    return user_to_dict(db, user)


def update_user(
    db: Session,
    user_id: str,
    updates: dict[str, object],
) -> dict[str, object]:
    user = db.get(User, user_id)
    if user is None:
        raise not_found("用户不存在")

    next_role_ids: list[str] | None = None
    if "role_ids" in updates and updates["role_ids"] is not None:
        next_role_ids = _validate_role_ids(db, list(updates["role_ids"]))
    else:
        next_role_ids = [role.role_id for role in load_user_roles(db, user_id)]

    next_is_admin = ADMIN_SEED_ROLE_ID in next_role_ids
    _assert_admin_constraints(user, role_ids=next_role_ids, is_admin=next_is_admin)

    if "display_name" in updates and updates["display_name"] is not None:
        user.display_name = str(updates["display_name"]).strip()
    if "password" in updates and updates["password"] is not None:
        password = str(updates["password"]).strip()
        if password:
            user.password_hash = hash_password(password)
    user.is_admin = next_is_admin

    db.execute(UserRole.__table__.delete().where(UserRole.user_id == user_id))
    for role_id in next_role_ids:
        db.add(UserRole(user_id=user_id, role_id=role_id))

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise conflict("用户名已存在", field_errors={"username": "已占用"}) from exc
    db.refresh(user)
    return user_to_dict(db, user)


def delete_user(db: Session, user_id: str) -> None:
    user = db.get(User, user_id)
    if user is None:
        raise not_found("用户不存在")
    if user.user_id == ADMIN_SEED_USER_ID:
        raise forbidden("不可删除 admin 用户")
    db.execute(UserRole.__table__.delete().where(UserRole.user_id == user_id))
    db.delete(user)
    db.commit()
