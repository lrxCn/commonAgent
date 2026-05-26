"""KB multi-role: kb_document_meta doc_id PK + kb_document_roles junction."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "002_kb_multi_role"
down_revision: Union[str, None] = "001_initial_demo"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "_kb_document_role_backup",
        sa.Column("doc_id", sa.String(length=128), nullable=False),
        sa.Column("role_id", sa.String(length=64), nullable=False),
        sa.PrimaryKeyConstraint("doc_id", "role_id"),
    )
    op.execute(
        "INSERT INTO _kb_document_role_backup (doc_id, role_id) "
        "SELECT doc_id, role_id FROM kb_document_meta"
    )

    op.create_table(
        "kb_document_meta_new",
        sa.Column("doc_id", sa.String(length=128), nullable=False),
        sa.Column("doc_name", sa.String(length=255), nullable=False),
        sa.Column("version", sa.String(length=64), nullable=False),
        sa.Column("raw_content", sa.Text(), nullable=False),
        sa.Column("chunks_written", sa.Integer(), nullable=False),
        sa.Column("tokens_estimated", sa.Integer(), nullable=False),
        sa.Column("created_by", sa.String(length=64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.user_id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("doc_id"),
    )

    op.execute(
        """
        INSERT INTO kb_document_meta_new (
            doc_id, doc_name, version, raw_content, chunks_written,
            tokens_estimated, created_by, created_at, updated_at
        )
        SELECT
            m.doc_id,
            m.doc_name,
            m.version,
            m.raw_content,
            m.chunks_written,
            m.tokens_estimated,
            m.created_by,
            m.created_at,
            m.updated_at
        FROM kb_document_meta AS m
        INNER JOIN (
            SELECT doc_id, MAX(updated_at) AS max_updated
            FROM kb_document_meta
            GROUP BY doc_id
        ) AS latest
            ON m.doc_id = latest.doc_id AND m.updated_at = latest.max_updated
        """
    )

    op.drop_table("kb_document_meta")
    op.rename_table("kb_document_meta_new", "kb_document_meta")

    op.create_table(
        "kb_document_roles",
        sa.Column("doc_id", sa.String(length=128), nullable=False),
        sa.Column("role_id", sa.String(length=64), nullable=False),
        sa.ForeignKeyConstraint(["doc_id"], ["kb_document_meta.doc_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["role_id"], ["roles.role_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("doc_id", "role_id"),
    )
    op.execute(
        "INSERT INTO kb_document_roles (doc_id, role_id) "
        "SELECT doc_id, role_id FROM _kb_document_role_backup"
    )
    op.drop_table("_kb_document_role_backup")


def downgrade() -> None:
    op.create_table(
        "_kb_document_role_backup",
        sa.Column("doc_id", sa.String(length=128), nullable=False),
        sa.Column("role_id", sa.String(length=64), nullable=False),
        sa.PrimaryKeyConstraint("doc_id", "role_id"),
    )
    op.execute(
        "INSERT INTO _kb_document_role_backup (doc_id, role_id) "
        "SELECT doc_id, role_id FROM kb_document_roles"
    )
    op.drop_table("kb_document_roles")

    op.create_table(
        "kb_document_meta_old",
        sa.Column("doc_id", sa.String(length=128), nullable=False),
        sa.Column("role_id", sa.String(length=64), nullable=False),
        sa.Column("doc_name", sa.String(length=255), nullable=False),
        sa.Column("version", sa.String(length=64), nullable=False),
        sa.Column("raw_content", sa.Text(), nullable=False),
        sa.Column("chunks_written", sa.Integer(), nullable=False),
        sa.Column("tokens_estimated", sa.Integer(), nullable=False),
        sa.Column("created_by", sa.String(length=64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.user_id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["role_id"], ["roles.role_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("doc_id", "role_id"),
    )

    op.execute(
        """
        INSERT INTO kb_document_meta_old (
            doc_id, role_id, doc_name, version, raw_content, chunks_written,
            tokens_estimated, created_by, created_at, updated_at
        )
        SELECT
            m.doc_id,
            b.role_id,
            m.doc_name,
            m.version,
            m.raw_content,
            m.chunks_written,
            m.tokens_estimated,
            m.created_by,
            m.created_at,
            m.updated_at
        FROM kb_document_meta AS m
        INNER JOIN _kb_document_role_backup AS b ON m.doc_id = b.doc_id
        """
    )

    op.drop_table("kb_document_meta")
    op.rename_table("kb_document_meta_old", "kb_document_meta")
    op.drop_table("_kb_document_role_backup")
