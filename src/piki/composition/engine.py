from pydantic import Field

from piki.composition.contracts import (
    ConversationTurn,
    LLMAdapterError,
)
from piki.composition.grounding import (
    GroundingFailure,
    GroundingValidator,
    factual_fallback,
)
from piki.composition.service import ResponseComposer
from piki.domain.contracts import ContextPacket, ContractModel, ResponseMode
from piki.observability.events import (
    EventOutcome,
    LifecycleEvent,
    LifecycleObserver,
)


class ResponseOutcome(ContractModel):
    text: str = Field(min_length=1, max_length=4096)
    mode: ResponseMode
    used_fallback: bool
    grounding_failures: tuple[GroundingFailure, ...] = ()
    provider_response_id: str | None = Field(default=None, max_length=255)
    trace_id: str = Field(min_length=1, max_length=128)


class ResponseEngine:
    def __init__(
        self,
        composer: ResponseComposer,
        validator: GroundingValidator | None = None,
        observer: LifecycleObserver | None = None,
    ) -> None:
        self._composer = composer
        self._validator = validator or GroundingValidator()
        self._observer = observer or LifecycleObserver()

    async def respond(
        self,
        packet: ContextPacket,
        *,
        conversation: tuple[ConversationTurn, ...] = (),
        deterministic_text: str | None = None,
    ) -> ResponseOutcome:
        self._observer.emit(
            LifecycleEvent.CONTEXT_BUILT,
            trace_id=packet.trace_id,
            component="context_packet",
            outcome=EventOutcome.SUCCEEDED,
            confirmed_count=len(packet.confirmed_data),
            unavailable_count=len(packet.unavailable_data),
        )
        if packet.response_mode is ResponseMode.JINJA:
            return self._fallback(packet)

        if packet.response_mode is ResponseMode.DETERMINISTIC:
            if deterministic_text is None:
                raise ValueError("deterministic response mode requires text")
            grounding_started = self._observer.started_at()
            validation = self._validator.validate(deterministic_text, packet)
            self._emit_grounding(packet, validation.failures, grounding_started)
            if not validation.safe or validation.text is None:
                return self._fallback(packet, validation.failures)
            return ResponseOutcome(
                text=validation.text,
                mode=packet.response_mode,
                used_fallback=False,
                trace_id=packet.trace_id,
            )

        llm_started = self._observer.started_at()
        self._observer.emit(
            LifecycleEvent.LLM_STARTED,
            trace_id=packet.trace_id,
            component="llm",
            outcome=EventOutcome.STARTED,
        )
        try:
            composed = await self._composer.compose(
                packet,
                conversation=conversation,
            )
        except LLMAdapterError as error:
            self._observer.emit(
                LifecycleEvent.LLM_FINISHED,
                trace_id=packet.trace_id,
                component="llm",
                outcome=EventOutcome.FAILED,
                started_at=llm_started,
                error_code=error.code.value,
            )
            return self._fallback(packet)

        self._observer.emit(
            LifecycleEvent.LLM_FINISHED,
            trace_id=packet.trace_id,
            component="llm",
            outcome=EventOutcome.SUCCEEDED,
            started_at=llm_started,
        )

        grounding_started = self._observer.started_at()
        validation = self._validator.validate(composed.text, packet)
        self._emit_grounding(packet, validation.failures, grounding_started)
        if not validation.safe or validation.text is None:
            return self._fallback(packet, validation.failures)
        return ResponseOutcome(
            text=validation.text,
            mode=packet.response_mode,
            used_fallback=False,
            provider_response_id=composed.provider_response_id,
            trace_id=packet.trace_id,
        )

    def _emit_grounding(
        self,
        packet: ContextPacket,
        failures: tuple[GroundingFailure, ...],
        started_at: float,
    ) -> None:
        self._observer.emit(
            LifecycleEvent.GROUNDING_CHECKED,
            trace_id=packet.trace_id,
            component="grounding",
            outcome=EventOutcome.BLOCKED if failures else EventOutcome.SUCCEEDED,
            started_at=started_at,
            error_code=failures[0].value if failures else None,
        )

    @staticmethod
    def _fallback(
        packet: ContextPacket,
        failures: tuple[GroundingFailure, ...] = (),
    ) -> ResponseOutcome:
        return ResponseOutcome(
            text=factual_fallback(packet),
            mode=packet.response_mode,
            used_fallback=True,
            grounding_failures=failures,
            trace_id=packet.trace_id,
        )
