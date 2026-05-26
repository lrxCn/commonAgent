"""Tests for Back demo database migrations and seed data."""

from __future__ import annotations

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import func, inspect, select
from sqlalchemy.orm import Session, sessionmaker

from db.models import Role, Student, User, UserRole
from db.seed import SEED_ROLES, admin_has_role_admin, run_seed
from db.session import create_engine_from_url, get_session_factory
from domain.role_id import is_valid_role_id, validate_role_id
from settings.config import Settings, set_settings_override


@pytest.fixture
def sqlite_database_url(tmp_path: Path) -> str:
    db_file = tmp_path / "demo.db"
    return f"sqlite+pysqlite:///{db_file}"


@pytest.fixture
def migrated_session_factory(
    sqlite_database_url: str,
) -> sessionmaker[Session]:
    back_root = Path(__file__).resolve().parents[1]
    alembic_cfg = Config(str(back_root / "alembic.ini"))
    alembic_cfg.set_main_option("script_location", str(back_root / "alembic"))
    alembic_cfg.set_main_option("sqlalchemy.url", sqlite_database_url)
    alembic_cfg.set_main_option("prepend_sys_path", str(back_root / "src"))

    set_settings_override(
        Settings(
            DATABASE_URL=sqlite_database_url,
            ADMIN_SEED_PASSWORD="123456",
        )
    )
    command.upgrade(alembic_cfg, "head")

    engine = create_engine_from_url(sqlite_database_url)
    session_factory = get_session_factory(engine)
    yield session_factory
    engine.dispose()
    set_settings_override(None)


def test_role_id_format_validation() -> None:
    assert is_valid_role_id("role-admin")
    assert is_valid_role_id("role-sales")
    assert not is_valid_role_id("admin")
    assert not is_valid_role_id("role-Admin")

    with pytest.raises(ValueError):
        validate_role_id("invalid")


def test_initial_migration_creates_expected_tables(
    migrated_session_factory: sessionmaker[Session],
) -> None:
    engine = migrated_session_factory.kw["bind"]
    tables = set(inspect(engine).get_table_names())
    assert tables == {
        "alembic_version",
        "roles",
        "users",
        "user_roles",
        "students",
        "kb_document_meta",
        "chat_threads",
    }


def test_seed_roles_users_students(
    migrated_session_factory: sessionmaker[Session],
) -> None:
    run_seed(migrated_session_factory, admin_password="123456")
    engine = migrated_session_factory.kw["bind"]

    with Session(engine) as session:
        role_ids = set(session.scalars(select(Role.role_id)).all())
        assert role_ids == {role_id for role_id, _, _ in SEED_ROLES}

        admin = session.scalar(select(User).where(User.username == "admin"))
        assert admin is not None
        assert admin.is_admin is True
        assert admin.user_id == "u-admin"

        admin_roles = set(
            session.scalars(
                select(UserRole.role_id).where(UserRole.user_id == admin.user_id)
            ).all()
        )
        assert admin_roles == {"role-admin"}
        assert admin_has_role_admin(session)

        usernames = set(session.scalars(select(User.username)).all())
        assert usernames == {"admin", "alice", "bob"}

        student_count = session.scalar(
            select(func.count()).select_from(Student)
        )
        assert student_count == 3

        student_nos = set(session.scalars(select(Student.student_no)).all())
        assert student_nos == {"2024001", "2024002", "2024003"}


def test_seed_is_idempotent(migrated_session_factory: sessionmaker[Session]) -> None:
    run_seed(migrated_session_factory, admin_password="123456")
    run_seed(migrated_session_factory, admin_password="123456")
    engine = migrated_session_factory.kw["bind"]

    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(Role)) == len(SEED_ROLES)
        assert session.scalar(select(func.count()).select_from(User)) == 3
        assert session.scalar(select(func.count()).select_from(Student)) == 3
