"""Add append-only delivery status events.

Revision ID: 0002_delivery_status_events
Revises: 0001_core_records
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_delivery_status_events"
down_revision: str | None = "0001_core_records"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "delivery_status_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("delivery_attempt_id", sa.Uuid(), nullable=False),
        sa.Column("provider_message_id", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.Column("error_message", sa.String(length=500), nullable=True),
        sa.Column("trace_id", sa.String(length=128), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["delivery_attempt_id"],
            ["delivery_attempts.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "provider_message_id",
            "status",
            name="uq_delivery_status_provider_state",
        ),
    )
    op.create_index(
        "ix_delivery_status_attempt_occurred",
        "delivery_status_events",
        ["delivery_attempt_id", "occurred_at"],
    )


def downgrade() -> None:
    op.drop_table("delivery_status_events")
