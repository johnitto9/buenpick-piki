from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class ConversationRecord(Base):
    __tablename__ = "conversations"
    __table_args__ = (
        UniqueConstraint(
            "channel",
            "channel_account_id",
            "external_conversation_id",
            name="uq_conversation_channel_identity",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    channel: Mapped[str] = mapped_column(String(32), nullable=False)
    channel_account_id: Mapped[str] = mapped_column(String(255), nullable=False)
    external_conversation_id: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default="piki_active"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class MessageRecord(Base):
    __tablename__ = "messages"
    __table_args__ = (
        UniqueConstraint("external_message_id", name="uq_messages_external_message_id"),
        Index("ix_messages_conversation_created", "conversation_id", "created_at"),
        Index("ix_messages_trace_id", "trace_id"),
        Index(
            "ix_messages_processing_available",
            "processing_status",
            "processing_available_at",
            "created_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    conversation_id: Mapped[UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False
    )
    external_message_id: Mapped[str | None] = mapped_column(String(255))
    direction: Mapped[str] = mapped_column(String(16), nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    content_text: Mapped[str | None] = mapped_column(Text)
    trace_id: Mapped[str] = mapped_column(String(128), nullable=False)
    processing_status: Mapped[str | None] = mapped_column(String(32))
    processing_attempts: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )
    processing_available_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    processing_claimed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    processing_error_code: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class HandoffRecord(Base):
    __tablename__ = "handoffs"
    __table_args__ = (
        UniqueConstraint(
            "conversation_id",
            "idempotency_key",
            name="uq_handoffs_conversation_idempotency",
        ),
        Index("ix_handoffs_status_created", "status", "created_at"),
        Index(
            "uq_handoffs_one_open_per_conversation",
            "conversation_id",
            unique=True,
            postgresql_where=text("status IN ('requested', 'claimed')"),
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    conversation_id: Mapped[UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False
    )
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default="requested"
    )
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    trace_id: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class DeliveryAttemptRecord(Base):
    __tablename__ = "delivery_attempts"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_delivery_attempts_idempotency_key"),
        Index("ix_delivery_attempts_provider_message_id", "provider_message_id"),
        Index("ix_delivery_attempts_trace_id", "trace_id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    conversation_id: Mapped[UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False
    )
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)
    provider_message_id: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(100))
    error_message: Mapped[str | None] = mapped_column(String(500))
    trace_id: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class DeliveryStatusEventRecord(Base):
    __tablename__ = "delivery_status_events"
    __table_args__ = (
        UniqueConstraint(
            "provider_message_id",
            "status",
            name="uq_delivery_status_provider_state",
        ),
        Index(
            "ix_delivery_status_attempt_occurred",
            "delivery_attempt_id",
            "occurred_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    delivery_attempt_id: Mapped[UUID] = mapped_column(
        ForeignKey("delivery_attempts.id", ondelete="CASCADE"), nullable=False
    )
    provider_message_id: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(100))
    error_message: Mapped[str | None] = mapped_column(String(500))
    trace_id: Mapped[str] = mapped_column(String(128), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
