"""Tests for KB multi-role Postgres data migration (task 97)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from db.models import KbDocumentMeta, KbDocumentRole
from db.seed import run_seed
from db.session import create_engine_from_url, get_session_factory
from services.kb_migration import (
    LegacyMetaRow,
    apply_postgres_kb_migration,
    build_postgres_migration_plan,
    is_legacy_kb_schema,
    merge_legacy_meta_rows,
)
from settings.config import Settings, set_settings_override

UTC = timezone.utc
T0 = datetime(2026, 1, 1, tzinfo=UTC)
T1 = T0 + timedelta(hours=1)
T2 = T0 + timedelta(hours=2)


def test_merge_legacy_meta_rows_picks_latest_scalar_fields() -> None:
    rows = [
        LegacyMetaRow(
            doc_id="doc-a",
            role_id="role-sales",
            doc_name="old-name",
            version="1",
            raw_content="old content",
            chunks_written=1,
            tokens_estimated=10,
            created_by="u-admin",
            created_at=T0,
            updated_at=T0,
        ),
        LegacyMetaRow(
            doc_id="doc-a",
            role_id="role-support",
            doc_name="new-name",
            version="2",
            raw_content="new content",
            chunks_written=5,
            tokens_estimated=50,
            created_by="u-admin",
            created_at=T1,
            updated_at=T2,
        ),
    ]

    merged = merge_legacy_meta_rows(rows)

    assert len(merged) == 1
    doc = merged[0]
    assert doc.doc_id == "doc-a"
    assert doc.role_ids == ("role-sales", "role-support")
    assert doc.doc_name == "new-name"
    assert doc.version == "2"
    assert doc.raw_content == "new content"
    assert doc.chunks_written == 5
    assert doc.tokens_estimated == 50
    assert doc.created_at == T0
    assert doc.updated_at == T2


def test_merge_legacy_meta_rows_keeps_single_role_doc() -> None:
    rows = [
        LegacyMetaRow(
            doc_id="doc-b",
            role_id="role-sales",
            doc_name="price-list",
            version="1",
            raw_content="prices",
            chunks_written=2,
            tokens_estimated=20,
            created_by=None,
            created_at=T0,
            updated_at=T0,
        )
    ]

    merged = merge_legacy_meta_rows(rows)

    assert len(merged) == 1
    assert merged[0].role_ids == ("role-sales",)


@pytest.fixture
def legacy_kb_database(tmp_path: Path) -> tuple[str, Config]:
    db_file = tmp_path / "legacy_kb.db"
    database_url = f"sqlite+pysqlite:///{db_file}"
    back_root = Path(__file__).resolve().parents[1]

    set_settings_override(
        Settings(
            DATABASE_URL=database_url,
            ADMIN_SEED_PASSWORD="123456",
        )
    )

    alembic_cfg = Config(str(back_root / "alembic.ini"))
    alembic_cfg.set_main_option("script_location", str(back_root / "alembic"))
    alembic_cfg.set_main_option("sqlalchemy.url", database_url)
    alembic_cfg.set_main_option("prepend_sys_path", str(back_root / "src"))
    command.upgrade(alembic_cfg, "001_initial_demo")

    engine = create_engine_from_url(database_url)
    session_factory = get_session_factory(engine)
    run_seed(session_factory, admin_password="123456")

    with Session(engine) as session:
        session.execute(
            text(
                """
                INSERT INTO kb_document_meta (
                    doc_id, role_id, doc_name, version, raw_content,
                    chunks_written, tokens_estimated, created_by, created_at, updated_at
                ) VALUES
                (
                    'doc-shared', 'role-sales', 'shared-old', '1', 'sales text',
                    1, 10, 'u-admin', :t0, :t0
                ),
                (
                    'doc-shared', 'role-support', 'shared-new', '2', 'support text',
                    3, 30, 'u-admin', :t1, :t2
                ),
                (
                    'doc-sales-only', 'role-sales', 'sales-only', '1', 'only sales',
                    2, 20, 'u-admin', :t0, :t0
                )
                """
            ),
            {"t0": T0, "t1": T1, "t2": T2},
        )
        session.commit()
    engine.dispose()

    yield database_url, alembic_cfg
    set_settings_override(None)


def test_postgres_migration_dry_run_reports_merge_plan(
    legacy_kb_database: tuple[str, Config],
) -> None:
    database_url, _ = legacy_kb_database
    engine = create_engine_from_url(database_url)
    try:
        assert is_legacy_kb_schema(engine) is True
        plan = build_postgres_migration_plan(engine)
        assert plan.legacy_row_count == 3
        assert plan.duplicate_doc_ids == ("doc-shared",)
        assert len(plan.merged_documents) == 2

        shared = next(doc for doc in plan.merged_documents if doc.doc_id == "doc-shared")
        assert shared.role_ids == ("role-sales", "role-support")
        assert shared.doc_name == "shared-new"
        assert shared.raw_content == "support text"

        result = apply_postgres_kb_migration(engine, dry_run=True)
        assert result.applied is False
        assert result.plan is not None
        assert is_legacy_kb_schema(engine) is True
    finally:
        engine.dispose()


def test_postgres_migration_apply_is_idempotent(
    legacy_kb_database: tuple[str, Config],
) -> None:
    database_url, _ = legacy_kb_database
    engine = create_engine_from_url(database_url)
    try:
        first = apply_postgres_kb_migration(engine, dry_run=False)
        assert first.applied is True
        assert is_legacy_kb_schema(engine) is False

        with Session(engine) as session:
            meta_rows = session.scalars(select(KbDocumentMeta)).all()
            assert len(meta_rows) == 2
            shared = session.scalar(
                select(KbDocumentMeta).where(KbDocumentMeta.doc_id == "doc-shared")
            )
            assert shared is not None
            assert shared.doc_name == "shared-new"
            assert shared.version == "2"
            assert shared.raw_content == "support text"

            shared_roles = set(
                session.scalars(
                    select(KbDocumentRole.role_id).where(
                        KbDocumentRole.doc_id == "doc-shared"
                    )
                ).all()
            )
            assert shared_roles == {"role-sales", "role-support"}

        second = apply_postgres_kb_migration(engine, dry_run=False)
        assert second.applied is False
        assert "already migrated" in second.message
    finally:
        engine.dispose()
