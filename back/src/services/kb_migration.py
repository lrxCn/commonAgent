"""KB multi-role Postgres data migration (M2).

Merges legacy ``kb_document_meta`` rows keyed by ``(doc_id, role_id)`` into one
meta row per ``doc_id`` plus ``kb_document_roles`` junction rows.

Schema DDL is handled by Alembic ``002_kb_multi_role``; this module provides
the merge plan/apply logic for standalone scripts, dry-run, and unit tests.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine


@dataclass(frozen=True)
class LegacyMetaRow:
    doc_id: str
    role_id: str
    doc_name: str
    version: str
    raw_content: str
    chunks_written: int
    tokens_estimated: int
    created_by: str | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class MergedDocumentMeta:
    doc_id: str
    doc_name: str
    version: str
    raw_content: str
    chunks_written: int
    tokens_estimated: int
    created_by: str | None
    created_at: datetime
    updated_at: datetime
    role_ids: tuple[str, ...]


@dataclass(frozen=True)
class PostgresMigrationPlan:
    legacy_row_count: int
    merged_documents: tuple[MergedDocumentMeta, ...]
    duplicate_doc_ids: tuple[str, ...]


@dataclass(frozen=True)
class PostgresMigrationResult:
    applied: bool
    message: str
    plan: PostgresMigrationPlan | None = None


def merge_legacy_meta_rows(rows: list[LegacyMetaRow]) -> list[MergedDocumentMeta]:
    """Merge legacy rows sharing ``doc_id``; scalar fields from latest ``updated_at``."""
    grouped: dict[str, list[LegacyMetaRow]] = {}
    for row in rows:
        grouped.setdefault(row.doc_id, []).append(row)

    merged: list[MergedDocumentMeta] = []
    for doc_id in sorted(grouped):
        group = grouped[doc_id]
        winner = max(group, key=lambda item: item.updated_at)
        role_ids = tuple(sorted({item.role_id for item in group}))
        merged.append(
            MergedDocumentMeta(
                doc_id=doc_id,
                doc_name=winner.doc_name,
                version=winner.version,
                raw_content=winner.raw_content,
                chunks_written=winner.chunks_written,
                tokens_estimated=winner.tokens_estimated,
                created_by=winner.created_by,
                created_at=min(item.created_at for item in group),
                updated_at=winner.updated_at,
                role_ids=role_ids,
            )
        )
    return merged


def is_legacy_kb_schema(engine: Engine) -> bool:
    """True when ``kb_document_meta`` still uses composite ``(doc_id, role_id)`` PK."""
    inspector = inspect(engine)
    if "kb_document_meta" not in inspector.get_table_names():
        return False
    columns = {column["name"] for column in inspector.get_columns("kb_document_meta")}
    return "role_id" in columns


def has_kb_document_roles_table(engine: Engine) -> bool:
    return "kb_document_roles" in inspect(engine).get_table_names()


def load_legacy_meta_rows(engine: Engine) -> list[LegacyMetaRow]:
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT doc_id, role_id, doc_name, version, raw_content,
                       chunks_written, tokens_estimated, created_by,
                       created_at, updated_at
                FROM kb_document_meta
                ORDER BY doc_id, role_id
                """
            )
        ).mappings()
        return [
            LegacyMetaRow(
                doc_id=str(row["doc_id"]),
                role_id=str(row["role_id"]),
                doc_name=str(row["doc_name"]),
                version=str(row["version"]),
                raw_content=str(row["raw_content"]),
                chunks_written=int(row["chunks_written"]),
                tokens_estimated=int(row["tokens_estimated"]),
                created_by=row["created_by"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
            for row in rows
        ]


def build_postgres_migration_plan(engine: Engine) -> PostgresMigrationPlan:
    legacy_rows = load_legacy_meta_rows(engine)
    merged = merge_legacy_meta_rows(legacy_rows)
    duplicate_doc_ids = tuple(
        sorted(
            {
                row.doc_id
                for row in legacy_rows
                if sum(1 for other in legacy_rows if other.doc_id == row.doc_id) > 1
            }
        )
    )
    return PostgresMigrationPlan(
        legacy_row_count=len(legacy_rows),
        merged_documents=tuple(merged),
        duplicate_doc_ids=duplicate_doc_ids,
    )


def apply_postgres_kb_migration(
    engine: Engine,
    *,
    dry_run: bool = True,
    alembic_cfg: Any | None = None,
) -> PostgresMigrationResult:
    """Migrate legacy meta to doc_id PK + junction table. Idempotent on new schema."""
    if not is_legacy_kb_schema(engine):
        if has_kb_document_roles_table(engine):
            return PostgresMigrationResult(
                applied=False,
                message="schema already migrated (kb_document_meta has doc_id PK only)",
            )
        return PostgresMigrationResult(
            applied=False,
            message="kb_document_meta missing role_id column and kb_document_roles table",
        )

    plan = build_postgres_migration_plan(engine)
    if dry_run:
        return PostgresMigrationResult(
            applied=False,
            message="dry-run: no changes written",
            plan=plan,
        )

    if engine.dialect.name == "postgresql":
        if alembic_cfg is None:
            msg = "alembic_cfg is required to apply migration on PostgreSQL"
            raise ValueError(msg)
        from alembic import command

        command.upgrade(alembic_cfg, "002_kb_multi_role")
        return PostgresMigrationResult(
            applied=True,
            message=(
                f"alembic 002_kb_multi_role applied: "
                f"{len(plan.merged_documents)} documents from {plan.legacy_row_count} legacy rows"
            ),
            plan=plan,
        )

    _apply_sqlite_legacy_migration(engine, plan)
    return PostgresMigrationResult(
        applied=True,
        message=f"migrated {len(plan.merged_documents)} documents from {plan.legacy_row_count} legacy rows",
        plan=plan,
    )


def _apply_sqlite_legacy_migration(engine: Engine, plan: PostgresMigrationPlan) -> None:
    """SQLite-only apply path for local tests and dry-run validation."""
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS _kb_document_role_backup (
                    doc_id VARCHAR(128) NOT NULL,
                    role_id VARCHAR(64) NOT NULL,
                    PRIMARY KEY (doc_id, role_id)
                )
                """
            )
        )
        conn.execute(text("DELETE FROM _kb_document_role_backup"))
        conn.execute(
            text(
                "INSERT INTO _kb_document_role_backup (doc_id, role_id) "
                "SELECT doc_id, role_id FROM kb_document_meta"
            )
        )

        conn.execute(text("DROP TABLE IF EXISTS kb_document_meta_new"))
        conn.execute(
            text(
                """
                CREATE TABLE kb_document_meta_new (
                    doc_id VARCHAR(128) NOT NULL PRIMARY KEY,
                    doc_name VARCHAR(255) NOT NULL,
                    version VARCHAR(64) NOT NULL,
                    raw_content TEXT NOT NULL,
                    chunks_written INTEGER NOT NULL,
                    tokens_estimated INTEGER NOT NULL,
                    created_by VARCHAR(64),
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(created_by) REFERENCES users(user_id) ON DELETE SET NULL
                )
                """
            )
        )

        for doc in plan.merged_documents:
            conn.execute(
                text(
                    """
                    INSERT INTO kb_document_meta_new (
                        doc_id, doc_name, version, raw_content, chunks_written,
                        tokens_estimated, created_by, created_at, updated_at
                    ) VALUES (
                        :doc_id, :doc_name, :version, :raw_content, :chunks_written,
                        :tokens_estimated, :created_by, :created_at, :updated_at
                    )
                    """
                ),
                {
                    "doc_id": doc.doc_id,
                    "doc_name": doc.doc_name,
                    "version": doc.version,
                    "raw_content": doc.raw_content,
                    "chunks_written": doc.chunks_written,
                    "tokens_estimated": doc.tokens_estimated,
                    "created_by": doc.created_by,
                    "created_at": doc.created_at,
                    "updated_at": doc.updated_at,
                },
            )

        conn.execute(text("DROP TABLE kb_document_meta"))
        conn.execute(text("ALTER TABLE kb_document_meta_new RENAME TO kb_document_meta"))

        conn.execute(text("DROP TABLE IF EXISTS kb_document_roles"))
        conn.execute(
            text(
                """
                CREATE TABLE kb_document_roles (
                    doc_id VARCHAR(128) NOT NULL,
                    role_id VARCHAR(64) NOT NULL,
                    PRIMARY KEY (doc_id, role_id),
                    FOREIGN KEY(doc_id) REFERENCES kb_document_meta(doc_id) ON DELETE CASCADE,
                    FOREIGN KEY(role_id) REFERENCES roles(role_id) ON DELETE CASCADE
                )
                """
            )
        )
        conn.execute(
            text(
                "INSERT INTO kb_document_roles (doc_id, role_id) "
                "SELECT doc_id, role_id FROM _kb_document_role_backup"
            )
        )
        conn.execute(text("DROP TABLE _kb_document_role_backup"))


def format_migration_plan(plan: PostgresMigrationPlan) -> str:
    lines = [
        f"legacy rows: {plan.legacy_row_count}",
        f"merged documents: {len(plan.merged_documents)}",
        f"duplicate doc_ids: {', '.join(plan.duplicate_doc_ids) or '(none)'}",
        "",
    ]
    for doc in plan.merged_documents:
        lines.append(
            f"  {doc.doc_id}: roles={list(doc.role_ids)} "
            f"doc_name={doc.doc_name!r} version={doc.version} "
            f"updated_at={doc.updated_at.isoformat()}"
        )
    return "\n".join(lines)
