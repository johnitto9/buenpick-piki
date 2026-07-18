from piki.core.config import Settings
from piki.db.conversations import ConversationRepository, PersistStatus
from piki.db.session import Database, create_database
from piki.delivery.service import CallbackApplyStatus, PostgresDeliveryStore
from piki.integrations.meta.webhook import (
    MetaIngressRetryableError,
    MetaWebhookEvents,
    WebhookIngestResult,
)
from piki.observability.events import LifecycleObserver, StructlogEventSink
from piki.state.coordination import (
    DedupStatus,
    RedisCoordination,
    create_redis_coordination,
)


class DefaultMetaWebhookIngress:
    def __init__(
        self,
        database: Database,
        coordination: RedisCoordination,
        observer: LifecycleObserver | None = None,
    ) -> None:
        self._database = database
        self._coordination = coordination
        self._deliveries = PostgresDeliveryStore(database, observer)

    async def ingest(self, events: MetaWebhookEvents) -> WebhookIngestResult:
        accepted_messages = 0
        duplicate_messages = 0
        durable_messages: list[tuple[str, str]] = []

        async with self._database.session() as session:
            repository = ConversationRepository(session)
            for message in events.messages:
                phone_number_id = message.metadata.get("phone_number_id")
                if not phone_number_id:
                    raise MetaIngressRetryableError(
                        "normalized message has no phone number ID"
                    )
                persisted = await repository.record_inbound(
                    channel_account_id=phone_number_id,
                    message=message,
                    trace_id=f"meta:{message.message_id}",
                    enqueue_processing=True,
                )
                durable_messages.append((phone_number_id, message.message_id))
                if persisted.status is PersistStatus.DUPLICATE:
                    duplicate_messages += 1
                else:
                    accepted_messages += 1

        for phone_number_id, message_id in durable_messages:
            dedup = await self._coordination.messages.claim(phone_number_id, message_id)
            if dedup is DedupStatus.UNAVAILABLE:
                # PostgreSQL already committed; cache failure cannot make the webhook unsafe.
                continue

        accepted_statuses = 0
        duplicate_statuses = 0
        ignored_statuses = 0
        for callback in events.statuses:
            result = await self._deliveries.apply_callback(callback)
            if result is CallbackApplyStatus.MISSING_ATTEMPT:
                raise MetaIngressRetryableError(
                    "delivery callback arrived before its durable attempt"
                )
            if result is CallbackApplyStatus.DUPLICATE:
                duplicate_statuses += 1
            elif result is CallbackApplyStatus.IGNORED_REGRESSION:
                ignored_statuses += 1
            else:
                accepted_statuses += 1

        return WebhookIngestResult(
            accepted_messages=accepted_messages,
            duplicate_messages=duplicate_messages,
            accepted_statuses=accepted_statuses,
            duplicate_statuses=duplicate_statuses,
            ignored_statuses=ignored_statuses,
        )

    async def close(self) -> None:
        await self._coordination.close()
        await self._database.close()


def create_default_meta_ingress(settings: Settings) -> DefaultMetaWebhookIngress:
    return DefaultMetaWebhookIngress(
        create_database(settings),
        create_redis_coordination(settings),
        LifecycleObserver(StructlogEventSink()),
    )
