from uuid import UUID, uuid4

from piki.delivery.service import (
    DeliveryAttemptSnapshot,
    DeliveryAttemptState,
    DeliveryClaim,
    IdempotentDeliveryService,
)
from piki.domain.contracts import (
    CustomerServiceWindow,
    DeliveryKind,
    DeliveryRequest,
    DeliveryResult,
    DeliveryStatus,
)
from piki.observability.events import (
    LifecycleEvent,
    LifecycleObserver,
    RecordingEventSink,
)


class GoldenDeliveryStore:
    def __init__(self, attempt: DeliveryAttemptSnapshot) -> None:
        self.attempt = attempt
        self.created = True
        self.finalized: list[DeliveryResult] = []

    async def claim(
        self,
        conversation_id: UUID,
        request: DeliveryRequest,
    ) -> DeliveryClaim:
        return DeliveryClaim(created=self.created, attempt=self.attempt)

    async def finalize(self, attempt_id: UUID, result: DeliveryResult) -> None:
        self.finalized.append(result)
        self.attempt = DeliveryAttemptSnapshot(
            id=attempt_id,
            state=DeliveryAttemptState(result.status.value),
            provider_message_id=result.provider_message_id,
            error_code=result.error_code,
            error_message=result.error_message,
            trace_id=result.trace_id,
        )
        self.created = False


class RejectingMetaAdapter:
    def __init__(self) -> None:
        self.calls = 0

    async def send(self, request: DeliveryRequest) -> DeliveryResult:
        self.calls += 1
        return DeliveryResult(
            status=DeliveryStatus.FAILED,
            error_code="META_131047",
            error_message="Meta rechazó el mensaje.",
            trace_id=request.trace_id,
        )


async def test_g013_meta_rejection_is_failed_and_replay_never_resends() -> None:
    attempt = DeliveryAttemptSnapshot(
        id=uuid4(),
        state=DeliveryAttemptState.PENDING,
        trace_id="trace-g013-meta-failure",
    )
    store = GoldenDeliveryStore(attempt)
    adapter = RejectingMetaAdapter()
    sink = RecordingEventSink()
    service = IdempotentDeliveryService(
        store,  # type: ignore[arg-type]
        adapter,
        observer=LifecycleObserver(sink),
    )
    request = DeliveryRequest(
        idempotency_key="golden-meta-failure-1",
        conversation_id="5492914000000",
        kind=DeliveryKind.TEXT,
        text="Mensaje grounded de prueba.",
        customer_service_window=CustomerServiceWindow.OPEN,
        trace_id="trace-g013-meta-failure",
    )

    first = await service.send(uuid4(), request)
    replay = await service.send(uuid4(), request)

    assert first.status is DeliveryStatus.FAILED
    assert first.error_code == "META_131047"
    assert replay.status is DeliveryStatus.FAILED
    assert replay.metadata["idempotent_replay"] is True
    assert adapter.calls == 1
    assert len(store.finalized) == 1
    assert LifecycleEvent.DELIVERY_SUCCEEDED not in {
        record.event for record in sink.records
    }
    assert [record.event for record in sink.records] == [
        LifecycleEvent.DELIVERY_ATTEMPTED,
        LifecycleEvent.DELIVERY_FAILED,
        LifecycleEvent.DELIVERY_ATTEMPTED,
        LifecycleEvent.DELIVERY_FAILED,
    ]
