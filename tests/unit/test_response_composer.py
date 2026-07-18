from piki.composition.contracts import (
    CompositionRequest,
    CompositionResult,
    ConversationTurn,
)
from piki.composition.service import ResponseComposer
from piki.domain.contracts import ContextPacket, ResponseMode


class RecordingLLM:
    def __init__(self) -> None:
        self.requests: list[CompositionRequest] = []

    async def compose(self, request: CompositionRequest) -> CompositionResult:
        self.requests.append(request)
        return CompositionResult(
            text="Respuesta fake para test.",
            provider_response_id="fake-response-1",
            model="fake-model",
            trace_id=request.trace_id,
        )


async def test_composer_builds_request_from_single_prompt_sources() -> None:
    adapter = RecordingLLM()
    composer = ResponseComposer(adapter)
    packet = ContextPacket(
        task="Explicar BuenPick.",
        query="¿Cómo funciona?",
        response_mode=ResponseMode.NON_COMMERCIAL_LLM,
        trace_id="trace-composer",
    )
    conversation = (ConversationTurn(role="user", text="Hola Piki"),)

    result = await composer.compose(packet, conversation=conversation)

    assert result.trace_id == "trace-composer"
    assert len(adapter.requests) == 1
    assert adapter.requests[0].conversation == conversation
    assert "Sos Piki" in adapter.requests[0].system_prompt
    assert '"¿Cómo funciona?"' in adapter.requests[0].evidence_prompt


async def test_composer_rejects_non_llm_modes_before_adapter() -> None:
    adapter = RecordingLLM()
    composer = ResponseComposer(adapter)
    packet = ContextPacket(
        task="Enviar imagen.",
        query="Foto",
        response_mode=ResponseMode.DETERMINISTIC,
        trace_id="trace-no-llm",
    )

    try:
        await composer.compose(packet)
    except ValueError as error:
        assert "does not permit" in str(error)
    else:
        raise AssertionError("deterministic mode must not call LLM")

    assert adapter.requests == []
