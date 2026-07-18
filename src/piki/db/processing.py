from datetime import UTC, datetime, timedelta
from enum import StrEnum
from uuid import UUID

from pydantic import Field
from sqlalchemy import and_, or_, select, update

from piki.db.models import ConversationRecord, MessageRecord
from piki.db.session import Database
from piki.domain.contracts import (
    Channel,
    ContractModel,
    InboundMessage,
    MessageKind,
)


class ProcessingStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class ClaimedInbound(ContractModel):
    message_record_id: UUID
    conversation_record_id: UUID
    channel_account_id: str = Field(min_length=1, max_length=255)
    message: InboundMessage
    attempts: int = Field(ge=1)


class PostgresMessageProcessingStore:
    def __init__(self, database: Database) -> None:
        self._database = database

    async def claim_next(self, *, claim_timeout_seconds: int) -> ClaimedInbound | None:
        now = datetime.now(UTC)
        stale_before = now - timedelta(seconds=claim_timeout_seconds)
        async with self._database.session() as session:
            statement = (
                select(MessageRecord, ConversationRecord)
                .join(
                    ConversationRecord,
                    ConversationRecord.id == MessageRecord.conversation_id,
                )
                .where(
                    MessageRecord.direction == "inbound",
                    or_(
                        and_(
                            MessageRecord.processing_status
                            == ProcessingStatus.PENDING.value,
                            MessageRecord.processing_available_at <= now,
                        ),
                        and_(
                            MessageRecord.processing_status
                            == ProcessingStatus.PROCESSING.value,
                            MessageRecord.processing_claimed_at <= stale_before,
                        ),
                    ),
                )
                .order_by(MessageRecord.processing_available_at, MessageRecord.created_at)
                .with_for_update(skip_locked=True, of=MessageRecord)
                .limit(1)
            )
            row = (await session.execute(statement)).one_or_none()
            if row is None:
                return None
            record, conversation = row.tuple()
            record.processing_status = ProcessingStatus.PROCESSING.value
            record.processing_attempts += 1
            record.processing_claimed_at = now
            record.processing_error_code = None
            if record.external_message_id is None:
                raise RuntimeError("processable inbound message has no external ID")
            return ClaimedInbound(
                message_record_id=record.id,
                conversation_record_id=conversation.id,
                channel_account_id=conversation.channel_account_id,
                message=InboundMessage(
                    message_id=record.external_message_id,
                    channel=Channel(conversation.channel),
                    conversation_id=conversation.external_conversation_id,
                    sender_id=conversation.external_conversation_id,
                    kind=MessageKind(record.kind),
                    text=record.content_text,
                    received_at=record.created_at,
                ),
                attempts=record.processing_attempts,
            )

    async def complete(self, message_record_id: UUID) -> None:
        await self._transition(
            message_record_id,
            status=ProcessingStatus.COMPLETED,
            error_code=None,
        )

    async def fail(
        self,
        message_record_id: UUID,
        *,
        error_code: str,
        retry: bool,
        retry_delay_seconds: float = 1.0,
    ) -> None:
        status = ProcessingStatus.PENDING if retry else ProcessingStatus.FAILED
        available_at = (
            datetime.now(UTC) + timedelta(seconds=retry_delay_seconds)
            if retry
            else None
        )
        await self._transition(
            message_record_id,
            status=status,
            error_code=error_code,
            available_at=available_at,
        )

    async def _transition(
        self,
        message_record_id: UUID,
        *,
        status: ProcessingStatus,
        error_code: str | None,
        available_at: datetime | None = None,
    ) -> None:
        statement = (
            update(MessageRecord)
            .where(
                MessageRecord.id == message_record_id,
                MessageRecord.processing_status == ProcessingStatus.PROCESSING.value,
            )
            .values(
                processing_status=status.value,
                processing_available_at=available_at,
                processing_claimed_at=None,
                processing_error_code=error_code,
            )
            .returning(MessageRecord.id)
        )
        async with self._database.session() as session:
            updated = (await session.scalars(statement)).one_or_none()
            if updated is None:
                raise RuntimeError("message processing claim is no longer active")
