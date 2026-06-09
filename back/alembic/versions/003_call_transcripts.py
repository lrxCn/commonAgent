"""Call transcript persistence with summary and sensitive keyword hits."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "003_call_transcripts"
down_revision: Union[str, None] = "002_kb_multi_role"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "call_transcripts",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("call_id", sa.String(length=128), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("peer_user_id", sa.String(length=64), nullable=False),
        sa.Column("peer_display_name", sa.String(length=128), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("sensitive_hits", sa.JSON(), nullable=False),
        sa.Column("lines", sa.JSON(), nullable=False),
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
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "call_id", name="uq_call_transcripts_user_call"),
    )
    op.create_index("ix_call_transcripts_call_id", "call_transcripts", ["call_id"])
    op.create_index("ix_call_transcripts_user_id", "call_transcripts", ["user_id"])
    op.create_index(
        "ix_call_transcripts_peer_user_id", "call_transcripts", ["peer_user_id"]
    )
    op.create_index("ix_call_transcripts_ended_at", "call_transcripts", ["ended_at"])


def downgrade() -> None:
    op.drop_index("ix_call_transcripts_ended_at", table_name="call_transcripts")
    op.drop_index("ix_call_transcripts_peer_user_id", table_name="call_transcripts")
    op.drop_index("ix_call_transcripts_user_id", table_name="call_transcripts")
    op.drop_index("ix_call_transcripts_call_id", table_name="call_transcripts")
    op.drop_table("call_transcripts")
