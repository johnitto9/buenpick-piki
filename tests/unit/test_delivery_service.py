from datetime import UTC, datetime
from typing import cast
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from piki.db.session import Database
from piki.delivery.service import (
    CallbackApplyStatus,
    DeliveryAttemptSnapshot,
    DeliveryAttemptState,
    DeliveryClaim,
    IdempotentDeliveryService,
    PostgresDeliveryStore,
)
from piki.domain.contracts import (
    DeliveryKind,
    DeliveryRequest,
    DeliveryResult,
    DeliveryStatus,
)
from piki.integrations.meta.webhook import MetaStatusUpdate
from piki.observability.events import (
    EventOutcome,
    LifecycleEvent,
    LifecycleObserver,
    LifecycleRecord,
    RecordingEventSink,
)


def request() -> DeliveryRequest:
    return DeliveryRequest(
        idempotency_key="delivery-idempotent-test",
        conversation_id="conversation-external-test",
        kind=DeliveryKind.TEXT,
        text="Mensaje confirmado.",
        trace_id="trace-delivery-test",
    )


class FakeDeliveryStore:
    def __init__(self, claim: DeliveryClaim) -> None:
        self.claim_result = claim
        self.claim_calls = 0
        self.finalized: list[tuple[UUID, DeliveryResult]] = []

    async def claim(
        self, conversation_id: UUID, delivery_request: DeliveryRequest
    ) -> DeliveryClaim:
        self.claim_calls += 1
        return self.claim_result

    async def finalize(self, attempt_id: UUID, result: DeliveryResult) -> None:
        self.finalized.append((attempt_id, result))

    async def apply_callback(self, callback: MetaStatusUpdate) -> object:
        raise AssertionError("not used by delivery service unit tests")


class FakeDeliveryAdapter:
    def __init__(self, result: DeliveryResult) -> None:
        self.result = result
        self.calls = 0

    async def send(self, delivery_request: DeliveryRequest) -> DeliveryResult:
        self.calls += 1
        return self.result


class OrderedSink:
    def __init__(self, order: list[str]) -> None:
        self.order = order
        self.records: list[LifecycleRecord] = []

    def emit(self, record: LifecycleRecord) -> None:
        self.order.append("emit")
        self.records.append(record)


class TrackingSessionContext:
    def __init__(self, order: list[str], *, fail_commit: bool = False) -> None:
        self.order = order
        self.fail_commit = fail_commit

    async def __aenter__(self) -> AsyncSession:
        self.order.append("enter")
        return cast(AsyncSession, object())

    async def __aexit__(self, *_: object) -> None:
        self.order.append("commit")
        if self.fail_commit:
            raise RuntimeError("simulated commit failure")


class TrackingDatabase:
    def __init__(self, order: list[str], *, fail_commit: bool = False) -> None:
        self.order = order
        self.fail_commit = fail_commit

    def session(self) -> TrackingSessionContext:
        return TrackingSessionContext(self.order, fail_commit=self.fail_commit)


class CallbackStoreStub(PostgresDeliveryStore):
    def __init__(
        self,
        *,
        result: CallbackApplyStatus,
        order: list[str],
        sink: OrderedSink,
        fail_commit: bool = False,
    ) -> None:
        super().__init__(
            cast(Database, TrackingDatabase(order, fail_commit=fail_commit)),
            LifecycleObserver(sink),
        )
        self.result = result
        self.order = order

    async def _apply_callback(
        self,
        session: AsyncSession,
        callback: MetaStatusUpdate,
    ) -> tuple[CallbackApplyStatus, str | None]:
        self.order.append("apply")
        return self.result, "trace-delivery-callback-test"


def callback(status: DeliveryStatus) -> MetaStatusUpdate:
    failed = status is DeliveryStatus.FAILED
    return MetaStatusUpdate(
        provider_message_id="wamid.callback.test",
        phone_number_id="phone-test",
        recipient_id="recipient-test",
        status=status,
        occurred_at=datetime(2026, 7, 17, tzinfo=UTC),
        error_code="131047" if failed else None,
        error_message="Sanitized Meta rejection." if failed else None,
    )


def snapshot(state: DeliveryAttemptState) -> DeliveryAttemptSnapshot:
    error_code = "META_100" if state is DeliveryAttemptState.FAILED else None
    return DeliveryAttemptSnapshot(
        id=uuid4(),
        state=state,
        provider_message_id=(
            "wamid.persisted.1"
            if state
            in {
                DeliveryAttemptState.ACCEPTED,
                DeliveryAttemptState.SENT,
                DeliveryAttemptState.DELIVERED,
                DeliveryAttemptState.READ,
            }
            else None
        ),
        error_code=error_code,
        error_message="Meta rechazó el mensaje." if error_code else None,
        trace_id="trace-delivery-test",
    )


async def test_first_claim_sends_once_and_persists_result() -> None:
    pending = snapshot(DeliveryAttemptState.PENDING)
    store = FakeDeliveryStore(DeliveryClaim(created=True, attempt=pending))
    accepted = DeliveryResult(
        status=DeliveryStatus.ACCEPTED,
        provider_message_id="wamid.new.1",
        trace_id="trace-delivery-test",
    )
    adapter = FakeDeliveryAdapter(accepted)
    service = IdempotentDeliveryService(store, adapter)

    result = await service.send(uuid4(), request())

    assert result == accepted
    assert adapter.calls == 1
    assert store.finalized == [(pending.id, accepted)]


async def test_replay_returns_persisted_acceptance_without_adapter_call() -> None:
    existing = snapshot(DeliveryAttemptState.ACCEPTED)
    store = FakeDeliveryStore(DeliveryClaim(created=False, attempt=existing))
    adapter = FakeDeliveryAdapter(
        DeliveryResult(
            status=DeliveryStatus.FAILED,
            error_code="SHOULD_NOT_RUN",
            trace_id="trace-delivery-test",
        )
    )
    service = IdempotentDeliveryService(store, adapter)

    result = await service.send(uuid4(), request())

    assert result.status is DeliveryStatus.ACCEPTED
    assert result.provider_message_id == "wamid.persisted.1"
    assert result.metadata["idempotent_replay"] is True
    assert adapter.calls == 0
    assert store.finalized == []


async def test_pending_replay_is_unknown_and_never_resends() -> None:
    store = FakeDeliveryStore(
        DeliveryClaim(created=False, attempt=snapshot(DeliveryAttemptState.PENDING))
    )
    adapter = FakeDeliveryAdapter(
        DeliveryResult(
            status=DeliveryStatus.ACCEPTED,
            provider_message_id="wamid.must-not-send",
            trace_id="trace-delivery-test",
        )
    )

    result = await IdempotentDeliveryService(store, adapter).send(uuid4(), request())

    assert result.status is DeliveryStatus.UNKNOWN
    assert result.error_code == "DELIVERY_ALREADY_IN_PROGRESS"
    assert adapter.calls == 0


def test_delivery_state_machine_allows_progress_and_rejects_regression() -> None:
    can_transition = PostgresDeliveryStore._can_transition

    assert can_transition(DeliveryAttemptState.ACCEPTED, DeliveryAttemptState.SENT)
    assert can_transition(DeliveryAttemptState.ACCEPTED, DeliveryAttemptState.DELIVERED)
    assert can_transition(DeliveryAttemptState.SENT, DeliveryAttemptState.READ)
    assert can_transition(DeliveryAttemptState.DELIVERED, DeliveryAttemptState.READ)
    assert not can_transition(DeliveryAttemptState.DELIVERED, DeliveryAttemptState.SENT)
    assert not can_transition(DeliveryAttemptState.READ, DeliveryAttemptState.FAILED)
    assert not can_transition(DeliveryAttemptState.FAILED, DeliveryAttemptState.DELIVERED)


async def test_acceptance_is_observed_as_attempt_not_false_delivery_success() -> None:
    pending = snapshot(DeliveryAttemptState.PENDING)
    store = FakeDeliveryStore(DeliveryClaim(created=True, attempt=pending))
    accepted = DeliveryResult(
        status=DeliveryStatus.ACCEPTED,
        provider_message_id="wamid.observed.acceptance",
        trace_id="trace-delivery-test",
    )
    sink = RecordingEventSink()

    await IdempotentDeliveryService(
        store,
        FakeDeliveryAdapter(accepted),
        observer=LifecycleObserver(sink),
    ).send(uuid4(), request())

    assert [record.event for record in sink.records] == [
        LifecycleEvent.DELIVERY_ATTEMPTED
    ]
    assert sink.records[0].outcome is EventOutcome.SUCCEEDED
    assert sink.records[0].duration_ms >= 0


async def test_failed_delivery_emits_attempt_and_failure_with_error_code() -> None:
    pending = snapshot(DeliveryAttemptState.PENDING)
    store = FakeDeliveryStore(DeliveryClaim(created=True, attempt=pending))
    failed = DeliveryResult(
        status=DeliveryStatus.FAILED,
        error_code="META_100",
        error_message="Meta rechazó el mensaje.",
        trace_id="trace-delivery-test",
    )
    sink = RecordingEventSink()

    await IdempotentDeliveryService(
        store,
        FakeDeliveryAdapter(failed),
        observer=LifecycleObserver(sink),
    ).send(uuid4(), request())

    assert [record.event for record in sink.records] == [
        LifecycleEvent.DELIVERY_ATTEMPTED,
        LifecycleEvent.DELIVERY_FAILED,
    ]
    assert all(record.outcome is EventOutcome.FAILED for record in sink.records)
    assert all(record.error_code == "META_100" for record in sink.records)
    assert LifecycleEvent.DELIVERY_SUCCEEDED not in {
        record.event for record in sink.records
    }


@pytest.mark.parametrize(
    ("status", "event", "outcome"),
    [
        (
            DeliveryStatus.DELIVERED,
            LifecycleEvent.DELIVERY_SUCCEEDED,
            EventOutcome.SUCCEEDED,
        ),
        (
            DeliveryStatus.FAILED,
            LifecycleEvent.DELIVERY_FAILED,
            EventOutcome.FAILED,
        ),
    ],
)
async def test_terminal_callback_is_observed_only_after_commit(
    status: DeliveryStatus,
    event: LifecycleEvent,
    outcome: EventOutcome,
) -> None:
    order: list[str] = []
    sink = OrderedSink(order)
    store = CallbackStoreStub(
        result=CallbackApplyStatus.APPLIED,
        order=order,
        sink=sink,
    )

    result = await store.apply_callback(callback(status))

    assert result is CallbackApplyStatus.APPLIED
    assert order == ["enter", "apply", "commit", "emit"]
    assert [record.event for record in sink.records] == [event]
    assert sink.records[0].outcome is outcome
    assert sink.records[0].trace_id == "trace-delivery-callback-test"
    assert sink.records[0].error_code == ("131047" if status is DeliveryStatus.FAILED else None)


@pytest.mark.parametrize(
    ("status", "apply_status"),
    [
        (DeliveryStatus.SENT, CallbackApplyStatus.APPLIED),
        (DeliveryStatus.READ, CallbackApplyStatus.APPLIED),
        (DeliveryStatus.DELIVERED, CallbackApplyStatus.DUPLICATE),
        (DeliveryStatus.FAILED, CallbackApplyStatus.IGNORED_REGRESSION),
    ],
)
async def test_non_terminal_or_unapplied_callback_emits_no_delivery_outcome(
    status: DeliveryStatus,
    apply_status: CallbackApplyStatus,
) -> None:
    order: list[str] = []
    sink = OrderedSink(order)
    store = CallbackStoreStub(result=apply_status, order=order, sink=sink)

    result = await store.apply_callback(callback(status))

    assert result is apply_status
    assert order == ["enter", "apply", "commit"]
    assert sink.records == []


async def test_commit_failure_cannot_emit_false_delivery_success() -> None:
    order: list[str] = []
    sink = OrderedSink(order)
    store = CallbackStoreStub(
        result=CallbackApplyStatus.APPLIED,
        order=order,
        sink=sink,
        fail_commit=True,
    )

    with pytest.raises(RuntimeError, match="simulated commit failure"):
        await store.apply_callback(callback(DeliveryStatus.DELIVERED))

    assert order == ["enter", "apply", "commit"]
    assert sink.records == []
