"""Make handoff requests idempotent and conversation-owned.

Revision ID: 0003_handoff_workflow
Revises: 0002_delivery_status_events
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_handoff_workflow"
down_revision: str | None = "0002_delivery_status_events"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "conversations",
        "status",
        existing_type=sa.String(length=32),
        server_default="piki_active",
        existing_nullable=False,
    )
    op.execute(
        sa.text("UPDATE conversations SET status = 'piki_active' WHERE status = 'active'")
    )

    op.add_column("handoffs", sa.Column("idempotency_key", sa.String(length=255)))
    op.execute(sa.text("UPDATE handoffs SET idempotency_key = CAST(id AS VARCHAR)"))
    op.alter_column(
        "handoffs",
        "idempotency_key",
        existing_type=sa.String(length=255),
        nullable=False,
    )
    op.create_unique_constraint(
        "uq_handoffs_conversation_idempotency",
        "handoffs",
        ["conversation_id", "idempotency_key"],
    )
    op.create_index(
        "uq_handoffs_one_open_per_conversation",
        "handoffs",
        ["conversation_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('requested', 'claimed')"),
    )


def downgrade() -> None:
    op.drop_index("uq_handoffs_one_open_per_conversation", table_name="handoffs")
    op.drop_constraint(
        "uq_handoffs_conversation_idempotency",
        "handoffs",
        type_="unique",
    )
    op.drop_column("handoffs", "idempotency_key")
    op.execute(
        sa.text("UPDATE conversations SET status = 'active' WHERE status = 'piki_active'")
    )
    op.alter_column(
        "conversations",
        "status",
        existing_type=sa.String(length=32),
        server_default="active",
        existing_nullable=False,
    )
