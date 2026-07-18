import unicodedata
from enum import StrEnum
from typing import Protocol, cast
from uuid import UUID

from pydantic import Field

from piki.composition.contracts import ConversationTurn, LLMAdapter
from piki.composition.engine import ResponseEngine
from piki.composition.service import ResponseComposer
from piki.core.config import Settings
from piki.db.conversations import ConversationRepository, PersistStatus, StoredMessage
from piki.db.handoffs import HandoffRepository, HandoffRequest
from piki.db.session import Database, create_database
from piki.domain.contracts import (
    Channel,
    ContractModel,
    InboundMessage,
    PerformedAction,
)
from piki.evidence.buenpick import search_result_evidence
from piki.integrations.buenpick.client import (
    BuenPickClient,
    BuenPickConfigurationError,
    create_buenpick_client,
)
from piki.integrations.llm.factory import create_llm_adapter
from piki.observability.events import (
    EventOutcome,
    LifecycleEvent,
    LifecycleObserver,
    StructlogEventSink,
)
from piki.prompts.policies import PolicyName, get_policy
from piki.state.active_pick import ConversationScope
from piki.state.coordination import (
    LockReleaseStatus,
    LockStatus,
    RedisCoordination,
    create_redis_coordination,
)
from piki.tools.buenpick import BuenPickTools


class ConversationIntent(StrEnum):
    GREETING = "greeting"
    DISCOVER_PICKS = "discover_picks"
    HUMAN_HANDOFF = "human_handoff"
    EXPLAIN_BUENPICK = "explain_buenpick"


class ConversationReply(ContractModel):
    conversation_id: UUID
    text: str = Field(min_length=1, max_length=4096)
    intent: ConversationIntent
    trace_id: str = Field(min_length=1, max_length=128)
    used_fallback: bool = False
    duplicate: bool = False


class ConversationBusyError(RuntimeError):
    pass


class AsyncClosable(Protocol):
    async def close(self) -> None: ...


def _normalized(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    plain = "".join(char for char in decomposed if not unicodedata.combining(char))
    return " ".join(plain.split())


class ConversationIntentResolver:
    _handoff_terms = ("humano", "persona", "operador", "asesor", "atencion")
    _search_terms = (
        "pick",
        "rescat",
        "busc",
        "disponible",
        "comida",
        "alimento",
        "hay",
        "quiero ",
    )
    _explain_terms = ("que es buenpick", "como funciona", "buenpick")
    _greetings = frozenset(
        {"hola", "buenas", "buen dia", "buenas tardes", "buenas noches", "hola piki"}
    )

    def resolve(self, text: str) -> ConversationIntent:
        normalized = _normalized(text)
        if any(term in normalized for term in self._handoff_terms):
            return ConversationIntent.HUMAN_HANDOFF
        if normalized in self._greetings:
            return ConversationIntent.GREETING
        if any(term in normalized for term in self._search_terms):
            return ConversationIntent.DISCOVER_PICKS
        if any(term in normalized for term in self._explain_terms):
            return ConversationIntent.EXPLAIN_BUENPICK
        return ConversationIntent.EXPLAIN_BUENPICK


class ConversationOrchestrator:
    def __init__(
        self,
        *,
        database: Database,
        coordination: RedisCoordination,
        engine: ResponseEngine,
        tools: BuenPickTools | None,
        resources: tuple[AsyncClosable, ...] = (),
        resolver: ConversationIntentResolver | None = None,
        observer: LifecycleObserver | None = None,
    ) -> None:
        self._database = database
        self._coordination = coordination
        self._engine = engine
        self._tools = tools
        self._resources = resources
        self._resolver = resolver or ConversationIntentResolver()
        self._observer = observer or LifecycleObserver()

    async def respond(
        self, message: InboundMessage, *, channel_account_id: str
    ) -> ConversationReply:
        self._observer.emit(
            LifecycleEvent.MESSAGE_RECEIVED,
            trace_id=f"conversation:{message.message_id}",
            component="conversation",
            outcome=EventOutcome.SUCCEEDED,
        )
        trace_id = f"conversation:{message.message_id}"
        scope = ConversationScope(
            channel=message.channel,
            channel_account_id=channel_account_id,
            conversation_id=message.conversation_id,
        )
        lease = await self._coordination.locks.acquire(scope)
        if lease.status is not LockStatus.ACQUIRED or lease.owner_token is None:
            raise ConversationBusyError("conversation is already being processed")
        try:
            return await self._respond_locked(
                message,
                channel_account_id=channel_account_id,
                trace_id=trace_id,
            )
        finally:
            released = await self._coordination.locks.release(scope, lease.owner_token)
            if released is LockReleaseStatus.UNAVAILABLE:
                self._observer.emit(
                    LifecycleEvent.INTENT_RESOLVED,
                    trace_id=trace_id,
                    component="conversation_lock",
                    outcome=EventOutcome.FAILED,
                    error_code="lock_release_unavailable",
                )

    async def history(
        self,
        *,
        channel: Channel,
        channel_account_id: str,
        conversation_id: str,
    ) -> tuple[StoredMessage, ...]:
        async with self._database.session() as session:
            repository = ConversationRepository(session)
            internal_id = await repository.find_conversation_id(
                channel=channel,
                channel_account_id=channel_account_id,
                external_conversation_id=conversation_id,
            )
            if internal_id is None:
                return ()
            return await repository.recent_messages(internal_id, limit=100)

    async def respond_persisted(
        self,
        message: InboundMessage,
        *,
        channel_account_id: str,
        conversation_record_id: UUID,
    ) -> ConversationReply:
        trace_id = f"conversation:{message.message_id}"
        self._observer.emit(
            LifecycleEvent.MESSAGE_RECEIVED,
            trace_id=trace_id,
            component="conversation_worker",
            outcome=EventOutcome.SUCCEEDED,
        )
        scope = ConversationScope(
            channel=message.channel,
            channel_account_id=channel_account_id,
            conversation_id=message.conversation_id,
        )
        lease = await self._coordination.locks.acquire(scope)
        if lease.status is not LockStatus.ACQUIRED or lease.owner_token is None:
            raise ConversationBusyError("conversation is already being processed")
        try:
            reply_external_id = f"piki-reply:{message.message_id}"
            async with self._database.session() as session:
                repository = ConversationRepository(session)
                existing = await repository.find_message(reply_external_id)
                if existing is not None and existing.content_text:
                    return ConversationReply(
                        conversation_id=conversation_record_id,
                        text=existing.content_text,
                        intent=self._resolver.resolve(message.text or ""),
                        trace_id=existing.trace_id,
                        duplicate=True,
                    )
                history = await repository.recent_messages(
                    conversation_record_id, limit=20
                )
            intent = self._resolver.resolve(message.text or "")
            self._observer.emit(
                LifecycleEvent.INTENT_RESOLVED,
                trace_id=trace_id,
                component=intent.value,
                outcome=EventOutcome.SUCCEEDED,
            )
            reply_text, used_fallback = await self._compose_reply(
                intent=intent,
                query=message.text or "",
                trace_id=trace_id,
                conversation_id=conversation_record_id,
                history=history,
                message_id=message.message_id,
            )
            async with self._database.session() as session:
                await ConversationRepository(session).record_outbound(
                    conversation_id=conversation_record_id,
                    text=reply_text,
                    trace_id=trace_id,
                    external_message_id=reply_external_id,
                )
            return ConversationReply(
                conversation_id=conversation_record_id,
                text=reply_text,
                intent=intent,
                trace_id=trace_id,
                used_fallback=used_fallback,
            )
        finally:
            await self._coordination.locks.release(scope, lease.owner_token)

    async def _respond_locked(
        self,
        message: InboundMessage,
        *,
        channel_account_id: str,
        trace_id: str,
    ) -> ConversationReply:
        reply_external_id = f"piki-reply:{message.message_id}"
        async with self._database.session() as session:
            repository = ConversationRepository(session)
            persisted = await repository.record_inbound(
                channel_account_id=channel_account_id,
                message=message,
                trace_id=trace_id,
            )
            if persisted.status is PersistStatus.DUPLICATE:
                existing = await repository.find_message(reply_external_id)
                if existing is not None and existing.content_text:
                    return ConversationReply(
                        conversation_id=persisted.conversation_id,
                        text=existing.content_text,
                        intent=self._resolver.resolve(message.text or ""),
                        trace_id=existing.trace_id,
                        duplicate=True,
                    )
                raise ConversationBusyError("duplicate message reply is not ready")
            history = await repository.recent_messages(persisted.conversation_id, limit=20)

        intent = self._resolver.resolve(message.text or "")
        self._observer.emit(
            LifecycleEvent.INTENT_RESOLVED,
            trace_id=trace_id,
            component=intent.value,
            outcome=EventOutcome.SUCCEEDED,
        )
        reply_text, used_fallback = await self._compose_reply(
            intent=intent,
            query=message.text or "",
            trace_id=trace_id,
            conversation_id=persisted.conversation_id,
            history=history,
            message_id=message.message_id,
        )

        async with self._database.session() as session:
            repository = ConversationRepository(session)
            await repository.record_outbound(
                conversation_id=persisted.conversation_id,
                text=reply_text,
                trace_id=trace_id,
                external_message_id=reply_external_id,
            )
        return ConversationReply(
            conversation_id=persisted.conversation_id,
            text=reply_text,
            intent=intent,
            trace_id=trace_id,
            used_fallback=used_fallback,
        )

    async def _compose_reply(
        self,
        *,
        intent: ConversationIntent,
        query: str,
        trace_id: str,
        conversation_id: UUID,
        history: tuple[StoredMessage, ...],
        message_id: str,
    ) -> tuple[str, bool]:
        turns = tuple(
            ConversationTurn(
                role="assistant" if item.direction == "outbound" else "user",
                text=item.content_text,
            )
            for item in history
            if item.content_text
        )
        if intent is ConversationIntent.HUMAN_HANDOFF:
            async with self._database.session() as session:
                await HandoffRepository(session).request(
                    HandoffRequest(
                        conversation_id=conversation_id,
                        idempotency_key=f"handoff:{message_id}",
                        reason="La persona solicitó atención humana.",
                        trace_id=trace_id,
                    )
                )
            policy = get_policy(PolicyName.HUMAN_HANDOFF)
            packet = policy.context_packet(
                query=query,
                trace_id=trace_id,
                actions_performed=(
                    PerformedAction(name="request_human_handoff", outcome="succeeded"),
                ),
            )
            outcome = await self._engine.respond(
                packet,
                conversation=turns,
                deterministic_text=(
                    "Listo, pedí atención humana. Tu conversación quedó en espera; "
                    "todavía no significa que una persona haya respondido."
                ),
            )
            return outcome.text, outcome.used_fallback

        if intent is ConversationIntent.DISCOVER_PICKS:
            if self._tools is None:
                return (
                    "Todavía no está configurado el acceso local a la API de BuenPick. "
                    "Puedo conversar, pero no voy a inventar picks, precios ni stock.",
                    True,
                )
            result = await self._tools.search_available_picks(
                query=query,
                commerce_id=None,
                trace_id=trace_id,
            )
            evidence = search_result_evidence(result)
            if not evidence.confirmed_data:
                return (
                    evidence.unavailable_data[0]
                    if evidence.unavailable_data
                    else "No pude confirmar picks disponibles en este momento.",
                    True,
                )
            policy = get_policy(PolicyName.DISCOVER_PICKS)
            packet = policy.context_packet(
                query=query,
                trace_id=trace_id,
                confirmed_data=evidence.confirmed_data,
                unavailable_data=evidence.unavailable_data,
                actions_performed=evidence.actions_performed,
            )
            outcome = await self._engine.respond(packet, conversation=turns)
            return outcome.text, outcome.used_fallback

        policy = get_policy(PolicyName.EXPLAIN_BUENPICK)
        packet = policy.context_packet(query=query, trace_id=trace_id)
        outcome = await self._engine.respond(packet, conversation=turns)
        return outcome.text, outcome.used_fallback

    async def close(self) -> None:
        for resource in reversed(self._resources):
            await resource.close()
        await self._coordination.close()
        await self._database.close()


def create_conversation_orchestrator(settings: Settings) -> ConversationOrchestrator:
    if not settings.conversation_enabled:
        raise ValueError("conversation runtime is disabled")
    observer = LifecycleObserver(StructlogEventSink())
    database = create_database(settings)
    coordination = create_redis_coordination(settings)
    llm_adapter: LLMAdapter = create_llm_adapter(settings)
    tools: BuenPickTools | None = None
    resources: list[AsyncClosable] = [cast(AsyncClosable, llm_adapter)]
    buenpick_client: BuenPickClient | None
    try:
        buenpick_client = create_buenpick_client(settings)
    except BuenPickConfigurationError:
        buenpick_client = None
    if buenpick_client is not None:
        resources.append(buenpick_client)
        tools = BuenPickTools(buenpick_client, observer)
    return ConversationOrchestrator(
        database=database,
        coordination=coordination,
        engine=ResponseEngine(
            ResponseComposer(llm_adapter, observer=observer),
            observer=observer,
        ),
        tools=tools,
        resources=tuple(resources),
        observer=observer,
    )
