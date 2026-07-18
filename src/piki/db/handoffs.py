from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import Field
from sqlalchemy import func, or_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from piki.db.models import ConversationRecord, HandoffRecord
from piki.domain.contracts import ContractModel


class HandoffStatus(StrEnum):
    REQUESTED = "requested"
    CLAIMED = "claimed"
    RESOLVED = "resolved"


class ConversationWorkflowStatus(StrEnum):
    NEW = "new"
    PIKI_ACTIVE = "piki_active"
    NEEDS_HUMAN = "needs_human"
    HUMAN_ACTIVE = "human_active"
    RESOLVED = "resolved"


class HandoffRequest(ContractModel):
    conversation_id: UUID
    idempotency_key: str = Field(min_length=1, max_length=255)
    reason: str = Field(min_length=1, max_length=500)
    trace_id: str = Field(min_length=1, max_length=128)


class PersistedHandoff(ContractModel):
    id: UUID
    conversation_id: UUID
    status: HandoffStatus
    reason: str
    trace_id: str
    created_at: datetime
    created: bool


class HandoffRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def request(self, request: HandoffRequest) -> PersistedHandoff:
        handoff_id = uuid4()
        statement = (
            insert(HandoffRecord)
            .values(
                id=handoff_id,
                conversation_id=request.conversation_id,
                idempotency_key=request.idempotency_key,
                status=HandoffStatus.REQUESTED.value,
                reason=request.reason,
                trace_id=request.trace_id,
            )
            .on_conflict_do_nothing()
            .returning(HandoffRecord)
        )
        row = (await self._session.scalars(statement)).one_or_none()
        created = row is not None
        if row is None:
            row = (
                await self._session.scalars(
                    select(HandoffRecord)
                    .where(
                        HandoffRecord.conversation_id == request.conversation_id,
                        or_(
                            HandoffRecord.idempotency_key == request.idempotency_key,
                            HandoffRecord.status.in_(
                                (HandoffStatus.REQUESTED.value, HandoffStatus.CLAIMED.value)
                            ),
                        ),
                    )
                    .order_by(HandoffRecord.created_at, HandoffRecord.id)
                    .limit(1)
                )
            ).one()

        await self._session.execute(
            update(ConversationRecord)
            .where(ConversationRecord.id == request.conversation_id)
            .values(
                status=ConversationWorkflowStatus.NEEDS_HUMAN.value,
                updated_at=func.now(),
            )
        )
        return PersistedHandoff(
            id=row.id,
            conversation_id=row.conversation_id,
            status=HandoffStatus(row.status),
            reason=row.reason,
            trace_id=row.trace_id,
            created_at=row.created_at,
            created=created,
        )
