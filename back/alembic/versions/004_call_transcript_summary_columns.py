"""Add summary, sensitive_hits, and updated_at to call_transcripts."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "004_transcript_summary"
down_revision: Union[str, None] = "003_call_transcripts"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_names(table: str) -> set[str]:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return {column["name"] for column in inspector.get_columns(table)}


def upgrade() -> None:
    columns = _column_names("call_transcripts")
    bind = op.get_bind()
    is_postgresql = bind.dialect.name == "postgresql"
    hits_default = sa.text("'[]'::json") if is_postgresql else sa.text("'[]'")

    if "summary" not in columns:
        op.add_column(
            "call_transcripts",
            sa.Column("summary", sa.Text(), server_default="", nullable=False),
        )

    if "sensitive_hits" not in columns:
        op.add_column(
            "call_transcripts",
            sa.Column(
                "sensitive_hits",
                sa.JSON(),
                server_default=hits_default,
                nullable=False,
            ),
        )

    added_updated_at = False
    if "updated_at" not in columns:
        op.add_column(
            "call_transcripts",
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("CURRENT_TIMESTAMP"),
                nullable=False,
            ),
        )
        added_updated_at = True

    if added_updated_at:
        op.execute(sa.text("UPDATE call_transcripts SET updated_at = created_at"))


def downgrade() -> None:
    # Repair migration: fresh installs get these columns from 003; do not drop them here.
    pass
