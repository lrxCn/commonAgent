"""Idempotent demo seed for roles, users, and sample students."""

from __future__ import annotations

import bcrypt
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from db.models import Role, Student, User, UserRole
from domain.role_id import validate_role_id

SEED_ROLES: tuple[tuple[str, str, str], ...] = (
    ("role-admin", "管理员", "演示平台管理员角色；独立工具与 RAG"),
    ("role-sales", "销售", "销售价目表等知识库"),
    ("role-support", "客服", "退换货政策等知识库"),
)

SEED_USERS: tuple[dict[str, object], ...] = (
    {
        "user_id": "u-admin",
        "username": "admin",
        "display_name": "Admin",
        "is_admin": True,
        "password": None,
        "role_ids": ("role-admin",),
    },
    {
        "user_id": "u-alice",
        "username": "alice",
        "display_name": "Alice",
        "is_admin": False,
        "password": "demo123",
        "role_ids": ("role-sales",),
    },
    {
        "user_id": "u-bob",
        "username": "bob",
        "display_name": "Bob",
        "is_admin": False,
        "password": "demo123",
        "role_ids": ("role-support",),
    },
)

SEED_STUDENTS: tuple[dict[str, str | None], ...] = (
    {
        "student_id": "s-demo-001",
        "student_no": "2024001",
        "name": "张三",
        "class_name": "高一(1)班",
        "status": "active",
        "created_by": "u-admin",
    },
    {
        "student_id": "s-demo-002",
        "student_no": "2024002",
        "name": "李四",
        "class_name": "高一(2)班",
        "status": "active",
        "created_by": "u-alice",
    },
    {
        "student_id": "s-demo-003",
        "student_no": "2024003",
        "name": "王五",
        "class_name": "高一(1)班",
        "status": "inactive",
        "created_by": "u-bob",
    },
)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _upsert_role(session: Session, role_id: str, name: str, description: str) -> None:
    validate_role_id(role_id)
    existing = session.get(Role, role_id)
    if existing is None:
        session.add(Role(role_id=role_id, name=name, description=description))
        return
    existing.name = name
    existing.description = description


def _upsert_user(
    session: Session,
    *,
    user_id: str,
    username: str,
    display_name: str,
    is_admin: bool,
    password: str,
    role_ids: tuple[str, ...],
) -> None:
    for role_id in role_ids:
        validate_role_id(role_id)

    existing = session.get(User, user_id)
    if existing is None:
        user = User(
            user_id=user_id,
            username=username,
            display_name=display_name,
            is_admin=is_admin,
            password_hash=hash_password(password),
        )
        session.add(user)
        session.flush()
    else:
        existing.username = username
        existing.display_name = display_name
        existing.is_admin = is_admin
        existing.password_hash = hash_password(password)
        session.execute(
            UserRole.__table__.delete().where(UserRole.user_id == user_id)
        )
        session.flush()

    for role_id in role_ids:
        session.merge(UserRole(user_id=user_id, role_id=role_id))


def _upsert_student(session: Session, payload: dict[str, str | None]) -> None:
    student_id = payload["student_id"]
    assert isinstance(student_id, str)
    existing = session.get(Student, student_id)
    if existing is None:
        session.add(Student(**payload))
        return
    for key, value in payload.items():
        setattr(existing, key, value)


def run_seed(session_factory: sessionmaker[Session], admin_password: str) -> None:
    """Seed demo roles, users, and students; safe to run on an empty or partial database."""
    with session_factory() as session:
        for role_id, name, description in SEED_ROLES:
            _upsert_role(session, role_id, name, description)
        session.flush()

        for spec in SEED_USERS:
            password = spec["password"]
            if password is None:
                password = admin_password
            assert isinstance(password, str)
            role_ids = spec["role_ids"]
            assert isinstance(role_ids, tuple)
            _upsert_user(
                session,
                user_id=str(spec["user_id"]),
                username=str(spec["username"]),
                display_name=str(spec["display_name"]),
                is_admin=bool(spec["is_admin"]),
                password=password,
                role_ids=role_ids,
            )

        for payload in SEED_STUDENTS:
            _upsert_student(session, payload)

        session.commit()


def admin_has_role_admin(session: Session) -> bool:
    row = session.scalar(
        select(UserRole.role_id)
        .join(User, User.user_id == UserRole.user_id)
        .where(User.username == "admin", UserRole.role_id == "role-admin")
    )
    return row == "role-admin"
