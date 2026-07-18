from datetime import UTC, datetime
from enum import StrEnum
from typing import cast
from uuid import UUID, uuid4

from pydantic import model_validator
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from piki.db.models import ConversationRecord, MessageRecord
from piki.domain.contracts import Channel, ContractModel, InboundMessage


class PersistStatus(StrEnum):
    CREATED = "created"
    DUPLICATE = "duplicate"


class PersistedInbound(ContractModel):
    status: PersistStatus
    conversation_id: UUID
    message_id: UUID | None = None

    @model_validator(mode="after")
    def validate_shape(self) -> "PersistedInbound":
        if (self.status is PersistStatus.CREATED) != (self.message_id is not None):
            raise ValueError("only created inbound records contain a message ID")
        return self


class StoredMessage(ContractModel):
    id: UUID
    external_message_id: str | None
    direction: str
    kind: str
    content_text: str | None
    trace_id: str
    created_at: datetime


class PersistedOutbound(ContractModel):
    message_id: UUID
    created: bool


class ConversationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def record_inbound(
        self,
        *,
        channel_account_id: str,
        message: InboundMessage,
        trace_id: str,
        enqueue_processing: bool = False,
    ) -> PersistedInbound:
        conversation_statement = (
            insert(ConversationRecord)
            .values(
                id=uuid4(),
                channel=message.channel.value,
                channel_account_id=channel_account_id,
                external_conversation_id=message.conversation_id,
                status="piki_active",
            )
            .on_conflict_do_update(
                constraint="uq_conversation_channel_identity",
                set_={"updated_at": func.now()},
            )
            .returning(ConversationRecord.id)
        )
        conversation_id = (
            await self._session.execute(conversation_statement)
        ).scalar_one()

        message_id = uuid4()
        message_statement = (
            insert(MessageRecord)
            .values(
                id=message_id,
                conversation_id=conversation_id,
                external_message_id=message.message_id,
                direction="inbound",
                kind=message.kind.value,
                content_text=message.text,
                trace_id=trace_id,
                processing_status="pending" if enqueue_processing else None,
                processing_available_at=(
                    datetime.now(UTC) if enqueue_processing else None
                ),
            )
            .on_conflict_do_nothing(constraint="uq_messages_external_message_id")
            .returning(MessageRecord.id)
        )
        stored_message_id = (
            await self._session.execute(message_statement)
        ).scalar_one_or_none()
        if stored_message_id is None:
            return PersistedInbound(
                status=PersistStatus.DUPLICATE,
                conversation_id=conversation_id,
            )
        return PersistedInbound(
            status=PersistStatus.CREATED,
            conversation_id=conversation_id,
            message_id=stored_message_id,
        )

    async def recent_messages(
        self, conversation_id: UUID, *, limit: int = 20
    ) -> tuple[StoredMessage, ...]:
        if limit < 1 or limit > 100:
            raise ValueError("message history limit must be between 1 and 100")
        statement = (
            select(MessageRecord)
            .where(MessageRecord.conversation_id == conversation_id)
            .order_by(MessageRecord.created_at.desc(), MessageRecord.id.desc())
            .limit(limit)
        )
        rows = (await self._session.scalars(statement)).all()
        return tuple(
            StoredMessage(
                id=row.id,
                external_message_id=row.external_message_id,
                direction=row.direction,
                kind=row.kind,
                content_text=row.content_text,
                trace_id=row.trace_id,
                created_at=row.created_at,
            )
            for row in reversed(rows)
        )

    async def find_conversation_id(
        self,
        *,
        channel: Channel,
        channel_account_id: str,
        external_conversation_id: str,
    ) -> UUID | None:
        return cast(
            UUID | None,
            await self._session.scalar(
                select(ConversationRecord.id).where(
                    ConversationRecord.channel == channel.value,
                    ConversationRecord.channel_account_id == channel_account_id,
                    ConversationRecord.external_conversation_id
                    == external_conversation_id,
                )
            )
        )

    async def record_outbound(
        self,
        *,
        conversation_id: UUID,
        text: str,
        trace_id: str,
        external_message_id: str,
    ) -> PersistedOutbound:
        message_id = uuid4()
        statement = (
            insert(MessageRecord)
            .values(
                id=message_id,
                conversation_id=conversation_id,
                external_message_id=external_message_id,
                direction="outbound",
                kind="text",
                content_text=text,
                trace_id=trace_id,
            )
            .on_conflict_do_nothing(constraint="uq_messages_external_message_id")
            .returning(MessageRecord.id)
        )
        stored_id = (await self._session.execute(statement)).scalar_one_or_none()
        if stored_id is not None:
            return PersistedOutbound(message_id=stored_id, created=True)
        existing_id = (
            await self._session.scalars(
                select(MessageRecord.id).where(
                    MessageRecord.external_message_id == external_message_id
                )
            )
        ).one()
        return PersistedOutbound(message_id=existing_id, created=False)

    async def find_message(self, external_message_id: str) -> StoredMessage | None:
        row = (
            await self._session.scalars(
                select(MessageRecord).where(
                    MessageRecord.external_message_id == external_message_id
                )
            )
        ).one_or_none()
        if row is None:
            return None
        return StoredMessage(
            id=row.id,
            external_message_id=row.external_message_id,
            direction=row.direction,
            kind=row.kind,
            content_text=row.content_text,
            trace_id=row.trace_id,
            created_at=row.created_at,
        )
