from piki.composition.contracts import (
    CompositionRequest,
    CompositionResult,
    ConversationTurn,
    LLMAdapter,
)
from piki.domain.contracts import ContextPacket, ResponseMode
from piki.observability.events import (
    EventOutcome,
    LifecycleEvent,
    LifecycleObserver,
)
from piki.prompts.renderer import PromptAssets


class ResponseComposer:
    def __init__(
        self,
        adapter: LLMAdapter,
        assets: PromptAssets | None = None,
        observer: LifecycleObserver | None = None,
    ) -> None:
        self._adapter = adapter
        self._assets = assets or PromptAssets()
        self._observer = observer or LifecycleObserver()

    async def compose(
        self,
        packet: ContextPacket,
        *,
        conversation: tuple[ConversationTurn, ...] = (),
    ) -> CompositionResult:
        if packet.response_mode not in {
            ResponseMode.JINJA_LLM,
            ResponseMode.NON_COMMERCIAL_LLM,
        }:
            raise ValueError("response mode does not permit LLM composition")
        render_started = self._observer.started_at()
        evidence_prompt = self._assets.render_evidence(packet)
        self._observer.emit(
            LifecycleEvent.TEMPLATE_RENDERED,
            trace_id=packet.trace_id,
            component="jinja",
            outcome=EventOutcome.SUCCEEDED,
            started_at=render_started,
        )
        request = CompositionRequest(
            system_prompt=self._assets.system_prompt,
            evidence_prompt=evidence_prompt,
            conversation=conversation,
            trace_id=packet.trace_id,
        )
        return await self._adapter.compose(request)
