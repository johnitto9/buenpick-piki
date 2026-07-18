"""Add durable inbound-message processing outbox.

Revision ID: 0004_message_processing_outbox
Revises: 0003_handoff_workflow
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_message_processing_outbox"
down_revision: str | None = "0003_handoff_workflow"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("messages", sa.Column("processing_status", sa.String(length=32)))
    op.add_column(
        "messages",
        sa.Column(
            "processing_attempts",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "messages",
        sa.Column("processing_available_at", sa.DateTime(timezone=True)),
    )
    op.add_column(
        "messages",
        sa.Column("processing_claimed_at", sa.DateTime(timezone=True)),
    )
    op.add_column(
        "messages",
        sa.Column("processing_error_code", sa.String(length=100)),
    )
    op.create_index(
        "ix_messages_processing_available",
        "messages",
        ["processing_status", "processing_available_at", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_messages_processing_available", table_name="messages")
    op.drop_column("messages", "processing_error_code")
    op.drop_column("messages", "processing_claimed_at")
    op.drop_column("messages", "processing_available_at")
    op.drop_column("messages", "processing_attempts")
    op.drop_column("messages", "processing_status")
