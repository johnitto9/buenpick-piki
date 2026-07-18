from datetime import UTC, datetime
from enum import StrEnum
from typing import Protocol
from uuid import UUID, uuid4

from pydantic import Field
from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from piki.db.models import DeliveryAttemptRecord, DeliveryStatusEventRecord
from piki.db.session import Database
from piki.domain.contracts import (
    ContractModel,
    DeliveryRequest,
    DeliveryResult,
    DeliveryStatus,
)
from piki.integrations.meta.webhook import MetaStatusUpdate
from piki.observability.events import (
    EventOutcome,
    LifecycleEvent,
    LifecycleObserver,
)


class DeliveryAttemptState(StrEnum):
    PENDING = "pending"
    UNKNOWN = "unknown"
    ACCEPTED = "accepted"
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"
    FAILED = "failed"


class DeliveryAttemptSnapshot(ContractModel):
    id: UUID
    state: DeliveryAttemptState
    provider_message_id: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    trace_id: str = Field(min_length=1, max_length=128)


class DeliveryClaim(ContractModel):
    created: bool
    attempt: DeliveryAttemptSnapshot


class CallbackApplyStatus(StrEnum):
    APPLIED = "applied"
    DUPLICATE = "duplicate"
    IGNORED_REGRESSION = "ignored_regression"
    MISSING_ATTEMPT = "missing_attempt"


class DeliveryAdapter(Protocol):
    async def send(self, request: DeliveryRequest) -> DeliveryResult: ...


class DeliveryStore(Protocol):
    async def claim(
        self, conversation_id: UUID, request: DeliveryRequest
    ) -> DeliveryClaim: ...

    async def finalize(self, attempt_id: UUID, result: DeliveryResult) -> None: ...

    async def apply_callback(self, callback: MetaStatusUpdate) -> CallbackApplyStatus: ...


class PostgresDeliveryStore:
    def __init__(
        self,
        database: Database,
        observer: LifecycleObserver | None = None,
    ) -> None:
        self._database = database
        self._observer = observer or LifecycleObserver()

    async def claim(
        self, conversation_id: UUID, request: DeliveryRequest
    ) -> DeliveryClaim:
        attempt_id = uuid4()
        statement = (
            insert(DeliveryAttemptRecord)
            .values(
                id=attempt_id,
                conversation_id=conversation_id,
                idempotency_key=request.idempotency_key,
                status=DeliveryAttemptState.PENDING.value,
                trace_id=request.trace_id,
            )
            .on_conflict_do_nothing(constraint="uq_delivery_attempts_idempotency_key")
            .returning(DeliveryAttemptRecord)
        )
        async with self._database.session() as session:
            created = (await session.scalars(statement)).one_or_none()
            if created is not None:
                return DeliveryClaim(created=True, attempt=self._snapshot(created))
            existing = (
                await session.scalars(
                    select(DeliveryAttemptRecord).where(
                        DeliveryAttemptRecord.idempotency_key == request.idempotency_key
                    )
                )
            ).one()
            return DeliveryClaim(created=False, attempt=self._snapshot(existing))

    async def finalize(self, attempt_id: UUID, result: DeliveryResult) -> None:
        statement = (
            update(DeliveryAttemptRecord)
            .where(
                DeliveryAttemptRecord.id == attempt_id,
                DeliveryAttemptRecord.status == DeliveryAttemptState.PENDING.value,
            )
            .values(
                provider_message_id=result.provider_message_id,
                status=result.status.value,
                error_code=result.error_code,
                error_message=result.error_message,
                updated_at=func.now(),
            )
            .returning(DeliveryAttemptRecord.id)
        )
        async with self._database.session() as session:
            updated_id = (await session.scalars(statement)).one_or_none()
            if updated_id is None:
                raise RuntimeError("delivery attempt is no longer pending")
            session.add(
                DeliveryStatusEventRecord(
                    delivery_attempt_id=attempt_id,
                    provider_message_id=result.provider_message_id,
                    status=result.status.value,
                    error_code=result.error_code,
                    error_message=result.error_message,
                    trace_id=result.trace_id,
                    occurred_at=datetime.now(UTC),
                )
            )

    async def apply_callback(self, callback: MetaStatusUpdate) -> CallbackApplyStatus:
        observed_at = self._observer.started_at()
        async with self._database.session() as session:
            result, trace_id = await self._apply_callback(session, callback)

        if result is CallbackApplyStatus.APPLIED and trace_id is not None:
            if callback.status is DeliveryStatus.DELIVERED:
                self._observer.emit(
                    LifecycleEvent.DELIVERY_SUCCEEDED,
                    trace_id=trace_id,
                    component="meta_delivery_callback",
                    outcome=EventOutcome.SUCCEEDED,
                    started_at=observed_at,
                )
            elif callback.status is DeliveryStatus.FAILED:
                self._observer.emit(
                    LifecycleEvent.DELIVERY_FAILED,
                    trace_id=trace_id,
                    component="meta_delivery_callback",
                    outcome=EventOutcome.FAILED,
                    started_at=observed_at,
                    error_code=callback.error_code,
                )
        return result

    async def _apply_callback(
        self,
        session: AsyncSession,
        callback: MetaStatusUpdate,
    ) -> tuple[CallbackApplyStatus, str | None]:
        attempt = (
            await session.scalars(
                select(DeliveryAttemptRecord).where(
                    DeliveryAttemptRecord.provider_message_id
                    == callback.provider_message_id
                )
            )
        ).one_or_none()
        if attempt is None:
            return CallbackApplyStatus.MISSING_ATTEMPT, None

        event_statement = (
            insert(DeliveryStatusEventRecord)
            .values(
                id=uuid4(),
                delivery_attempt_id=attempt.id,
                provider_message_id=callback.provider_message_id,
                status=callback.status.value,
                error_code=callback.error_code,
                error_message=callback.error_message,
                trace_id=attempt.trace_id,
                occurred_at=callback.occurred_at,
            )
            .on_conflict_do_nothing(constraint="uq_delivery_status_provider_state")
            .returning(DeliveryStatusEventRecord.id)
        )
        event_id = (await session.scalars(event_statement)).one_or_none()
        if event_id is None:
            return CallbackApplyStatus.DUPLICATE, attempt.trace_id

        current = DeliveryAttemptState(attempt.status)
        target = DeliveryAttemptState(callback.status.value)
        if not self._can_transition(current, target):
            return CallbackApplyStatus.IGNORED_REGRESSION, attempt.trace_id
        attempt.status = target.value
        attempt.error_code = callback.error_code
        attempt.error_message = callback.error_message
        attempt.updated_at = datetime.now(UTC)
        return CallbackApplyStatus.APPLIED, attempt.trace_id

    @staticmethod
    def _snapshot(record: DeliveryAttemptRecord) -> DeliveryAttemptSnapshot:
        return DeliveryAttemptSnapshot(
            id=record.id,
            state=DeliveryAttemptState(record.status),
            provider_message_id=record.provider_message_id,
            error_code=record.error_code,
            error_message=record.error_message,
            trace_id=record.trace_id,
        )

    @staticmethod
    def _can_transition(
        current: DeliveryAttemptState, target: DeliveryAttemptState
    ) -> bool:
        allowed = {
            DeliveryAttemptState.ACCEPTED: {
                DeliveryAttemptState.SENT,
                DeliveryAttemptState.DELIVERED,
                DeliveryAttemptState.READ,
                DeliveryAttemptState.FAILED,
            },
            DeliveryAttemptState.SENT: {
                DeliveryAttemptState.DELIVERED,
                DeliveryAttemptState.READ,
                DeliveryAttemptState.FAILED,
            },
            DeliveryAttemptState.DELIVERED: {DeliveryAttemptState.READ},
        }
        return target in allowed.get(current, set())


class IdempotentDeliveryService:
    def __init__(
        self,
        store: DeliveryStore,
        adapter: DeliveryAdapter,
        observer: LifecycleObserver | None = None,
    ) -> None:
        self._store = store
        self._adapter = adapter
        self._observer = observer or LifecycleObserver()

    async def send(
        self, conversation_id: UUID, request: DeliveryRequest
    ) -> DeliveryResult:
        observed_at = self._observer.started_at()
        claim = await self._store.claim(conversation_id, request)
        if not claim.created:
            result = self._existing_result(claim.attempt)
            self._emit_attempt(result, observed_at)
            return result
        result = await self._adapter.send(request)
        await self._store.finalize(claim.attempt.id, result)
        self._emit_attempt(result, observed_at)
        return result

    def _emit_attempt(self, result: DeliveryResult, started_at: float) -> None:
        failed = result.status in {DeliveryStatus.FAILED, DeliveryStatus.UNKNOWN}
        self._observer.emit(
            LifecycleEvent.DELIVERY_ATTEMPTED,
            trace_id=result.trace_id,
            component="meta_delivery",
            outcome=EventOutcome.FAILED if failed else EventOutcome.SUCCEEDED,
            started_at=started_at,
            error_code=result.error_code,
        )
        if failed:
            self._observer.emit(
                LifecycleEvent.DELIVERY_FAILED,
                trace_id=result.trace_id,
                component="meta_delivery",
                outcome=EventOutcome.FAILED,
                error_code=result.error_code,
            )

    @staticmethod
    def _existing_result(attempt: DeliveryAttemptSnapshot) -> DeliveryResult:
        if attempt.state is DeliveryAttemptState.PENDING:
            return DeliveryResult(
                status=DeliveryStatus.UNKNOWN,
                error_code="DELIVERY_ALREADY_IN_PROGRESS",
                error_message="Ya existe un intento de entrega en curso.",
                trace_id=attempt.trace_id,
                metadata={"idempotent_replay": True},
            )
        return DeliveryResult(
            status=DeliveryStatus(attempt.state.value),
            provider_message_id=attempt.provider_message_id,
            error_code=attempt.error_code,
            error_message=attempt.error_message,
            trace_id=attempt.trace_id,
            metadata={"idempotent_replay": True},
        )
