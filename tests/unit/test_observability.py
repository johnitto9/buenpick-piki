from piki.composition.contracts import CompositionRequest, CompositionResult
from piki.composition.engine import ResponseEngine
from piki.composition.service import ResponseComposer
from piki.domain.contracts import (
    ContextPacket,
    EvidenceItem,
    EvidenceSource,
    ResponseMode,
)
from piki.observability.events import (
    EventOutcome,
    LifecycleEvent,
    LifecycleObserver,
    RecordingEventSink,
)


class SafeLLM:
    async def compose(self, request: CompositionRequest) -> CompositionResult:
        return CompositionResult(
            text="Hay una opción confirmada para rescatar.",
            provider_response_id="observation-fixture",
            model="observation-model",
            trace_id=request.trace_id,
        )


def packet() -> ContextPacket:
    return ContextPacket(
        task="Responder con evidencia.",
        query="consulta privada de fixture",
        confirmed_data=(
            EvidenceItem(
                label="availability",
                value="Hay una opción confirmada para rescatar.",
                source=EvidenceSource.BUENPICK_INTERNAL_API,
            ),
        ),
        response_mode=ResponseMode.JINJA_LLM,
        trace_id="trace-observability",
    )


async def test_response_events_are_correlated_timed_and_pii_minimized() -> None:
    sink = RecordingEventSink()
    observer = LifecycleObserver(sink)
    engine = ResponseEngine(
        ResponseComposer(SafeLLM(), observer=observer),
        observer=observer,
    )

    outcome = await engine.respond(packet())

    assert outcome.used_fallback is False
    assert [record.event for record in sink.records] == [
        LifecycleEvent.CONTEXT_BUILT,
        LifecycleEvent.LLM_STARTED,
        LifecycleEvent.TEMPLATE_RENDERED,
        LifecycleEvent.LLM_FINISHED,
        LifecycleEvent.GROUNDING_CHECKED,
    ]
    assert {record.trace_id for record in sink.records} == {"trace-observability"}
    assert all(record.duration_ms >= 0 for record in sink.records)
    serialized = "\n".join(record.model_dump_json() for record in sink.records)
    assert "consulta privada" not in serialized
    assert "opción confirmada" not in serialized


async def test_grounding_block_has_distinct_observability_error() -> None:
    class UnsupportedLLM:
        async def compose(self, request: CompositionRequest) -> CompositionResult:
            return CompositionResult(
                text="Cuesta $9.999,00.",
                provider_response_id="unsupported-fixture",
                model="observation-model",
                trace_id=request.trace_id,
            )

    sink = RecordingEventSink()
    observer = LifecycleObserver(sink)
    engine = ResponseEngine(
        ResponseComposer(UnsupportedLLM(), observer=observer),
        observer=observer,
    )

    outcome = await engine.respond(packet())

    grounding = sink.records[-1]
    assert outcome.used_fallback is True
    assert grounding.event is LifecycleEvent.GROUNDING_CHECKED
    assert grounding.outcome is EventOutcome.BLOCKED
    assert grounding.error_code == "unsupported_high_risk_fact"
