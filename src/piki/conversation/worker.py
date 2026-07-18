from datetime import UTC, datetime, timedelta

from piki.conversation.service import (
    ConversationBusyError,
    ConversationOrchestrator,
    create_conversation_orchestrator,
)
from piki.core.config import Settings
from piki.db.processing import PostgresMessageProcessingStore
from piki.db.session import Database, create_database
from piki.delivery.service import IdempotentDeliveryService, PostgresDeliveryStore
from piki.domain.contracts import (
    CustomerServiceWindow,
    DeliveryKind,
    DeliveryRequest,
    DeliveryStatus,
)
from piki.integrations.meta.delivery import MetaDeliveryAdapter, create_meta_delivery_adapter
from piki.observability.events import LifecycleObserver, StructlogEventSink


class ConversationProcessingWorker:
    def __init__(
        self,
        *,
        settings: Settings,
        database: Database,
        orchestrator: ConversationOrchestrator,
        delivery_adapter: MetaDeliveryAdapter,
    ) -> None:
        self._settings = settings
        self._database = database
        self._store = PostgresMessageProcessingStore(database)
        self._orchestrator = orchestrator
        self._delivery_adapter = delivery_adapter
        observer = LifecycleObserver(StructlogEventSink())
        self._delivery = IdempotentDeliveryService(
            PostgresDeliveryStore(database, observer),
            delivery_adapter,
            observer,
        )

    async def process_once(self) -> bool:
        job = await self._store.claim_next(
            claim_timeout_seconds=(
                self._settings.conversation_worker_claim_timeout_seconds
            )
        )
        if job is None:
            return False
        try:
            reply = await self._orchestrator.respond_persisted(
                job.message,
                channel_account_id=job.channel_account_id,
                conversation_record_id=job.conversation_record_id,
            )
            window = (
                CustomerServiceWindow.OPEN
                if datetime.now(UTC) - job.message.received_at <= timedelta(hours=24)
                else CustomerServiceWindow.UNKNOWN
            )
            result = await self._delivery.send(
                job.conversation_record_id,
                DeliveryRequest(
                    idempotency_key=f"reply:{job.message.message_id}",
                    conversation_id=job.message.conversation_id,
                    kind=DeliveryKind.TEXT,
                    text=reply.text,
                    customer_service_window=window,
                    trace_id=reply.trace_id,
                ),
            )
            if result.status in {
                DeliveryStatus.ACCEPTED,
                DeliveryStatus.SENT,
                DeliveryStatus.DELIVERED,
                DeliveryStatus.READ,
            }:
                await self._store.complete(job.message_record_id)
            else:
                await self._store.fail(
                    job.message_record_id,
                    error_code=result.error_code or "delivery_failed",
                    retry=False,
                )
            return True
        except ConversationBusyError:
            await self._store.fail(
                job.message_record_id,
                error_code="conversation_busy",
                retry=job.attempts < self._settings.conversation_worker_max_attempts,
            )
            return True
        except Exception as error:
            await self._store.fail(
                job.message_record_id,
                error_code=type(error).__name__.casefold()[:100],
                retry=job.attempts < self._settings.conversation_worker_max_attempts,
            )
            return True

    async def close(self) -> None:
        await self._delivery_adapter.close()
        await self._orchestrator.close()
        await self._database.close()


def create_processing_worker(settings: Settings) -> ConversationProcessingWorker:
    if not settings.conversation_worker_enabled:
        raise ValueError("conversation worker is disabled")
    return ConversationProcessingWorker(
        settings=settings,
        database=create_database(settings),
        orchestrator=create_conversation_orchestrator(settings),
        delivery_adapter=create_meta_delivery_adapter(settings),
    )
