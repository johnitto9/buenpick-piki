import json
from collections.abc import Callable

import httpx
import pytest
from pydantic import SecretStr

from piki.composition.contracts import (
    CompositionRequest,
    ConversationTurn,
    LLMAdapterError,
    LLMErrorCode,
)
from piki.core.config import Settings
from piki.integrations.llm.openai_responses import (
    OpenAIResponsesAdapter,
    create_openai_responses_adapter,
)

Handler = Callable[[httpx.Request], httpx.Response]
TEST_KEY = "llm-contract-test-key"


def request() -> CompositionRequest:
    return CompositionRequest(
        system_prompt="Sos Piki. Usá sólo evidencia confirmada.",
        evidence_prompt="DATOS CONFIRMADOS\n- Pick: Rescate confirmado",
        conversation=(
            ConversationTurn(role="user", text="Hola"),
            ConversationTurn(role="assistant", text="¿Qué te gustaría rescatar?"),
        ),
        trace_id="trace-llm",
    )


def response_payload(
    *,
    status: str = "completed",
    content: list[dict[str, str | list[object]]] | None = None,
) -> dict[str, object]:
    output_content = content or [
        {"type": "output_text", "text": "Hay un rescate confirmado."}
    ]
    return {
        "id": "resp-test-1",
        "model": "model-test",
        "status": status,
        "output": [
            {
                "id": "msg-test-1",
                "type": "message",
                "role": "assistant",
                "content": output_content,
            }
        ],
    }


async def no_sleep(_: float) -> None:
    return None


def adapter_for(handler: Handler, *, max_attempts: int = 2) -> OpenAIResponsesAdapter:
    return OpenAIResponsesAdapter(
        base_url="https://llm.mock.invalid/v1",
        api_key=SecretStr(TEST_KEY),
        model="model-test",
        max_attempts=max_attempts,
        transport=httpx.MockTransport(handler),
        sleep=no_sleep,
    )


@pytest.mark.asyncio
async def test_responses_request_separates_instructions_evidence_and_history() -> None:
    observed: list[httpx.Request] = []

    def handler(http_request: httpx.Request) -> httpx.Response:
        observed.append(http_request)
        return httpx.Response(200, json=response_payload())

    async with adapter_for(handler) as adapter:
        result = await adapter.compose(request())

    body = json.loads(observed[0].content)
    assert observed[0].url.path == "/v1/responses"
    assert observed[0].headers["Authorization"] == f"Bearer {TEST_KEY}"
    assert body["model"] == "model-test"
    assert body["instructions"] == request().system_prompt
    assert body["input"][0] == {"role": "user", "content": "Hola"}
    assert body["input"][1]["role"] == "assistant"
    assert request().evidence_prompt in body["input"][-1]["content"]
    assert body["store"] is False
    assert "tools" not in body
    assert result.text == "Hay un rescate confirmado."
    assert result.provider_response_id == "resp-test-1"
    assert result.trace_id == "trace-llm"


@pytest.mark.asyncio
async def test_parser_collects_all_message_output_text_items() -> None:
    payload = response_payload(
        content=[
            {"type": "output_text", "text": "Primera parte."},
            {"type": "output_text", "text": "Segunda parte."},
        ]
    )
    payload["output"] = [
        {"type": "reasoning", "content": []},
        *payload["output"],  # type: ignore[operator]
    ]

    async with adapter_for(lambda _: httpx.Response(200, json=payload)) as adapter:
        result = await adapter.compose(request())

    assert result.text == "Primera parte.\nSegunda parte."


@pytest.mark.asyncio
async def test_retryable_error_is_bounded() -> None:
    statuses = iter((429, 200))
    calls = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        status = next(statuses)
        return httpx.Response(status, json=response_payload() if status == 200 else {})

    async with adapter_for(handler) as adapter:
        result = await adapter.compose(request())

    assert calls == 2
    assert result.text


@pytest.mark.asyncio
async def test_timeout_exhaustion_is_safe() -> None:
    calls = 0

    def handler(http_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        raise httpx.ReadTimeout("provider timeout detail", request=http_request)

    async with adapter_for(handler) as adapter:
        with pytest.raises(LLMAdapterError) as raised:
            await adapter.compose(request())

    assert calls == 2
    assert raised.value.code is LLMErrorCode.TIMEOUT
    assert "provider timeout" not in raised.value.user_safe_message


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status_code", "expected_code"),
    (
        (400, LLMErrorCode.BAD_REQUEST),
        (401, LLMErrorCode.UNAUTHORIZED),
        (429, LLMErrorCode.RATE_LIMITED),
        (503, LLMErrorCode.UNAVAILABLE),
    ),
)
async def test_http_errors_are_typed_and_do_not_leak_provider_body(
    status_code: int, expected_code: LLMErrorCode
) -> None:
    handler = lambda _: httpx.Response(  # noqa: E731
        status_code, json={"error": {"message": "private provider detail"}}
    )
    async with adapter_for(handler, max_attempts=1) as adapter:
        with pytest.raises(LLMAdapterError) as raised:
            await adapter.compose(request())

    assert raised.value.code is expected_code
    assert "private provider detail" not in raised.value.user_safe_message


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("payload", "expected_code"),
    (
        (response_payload(status="incomplete"), LLMErrorCode.INVALID_RESPONSE),
        (
            response_payload(content=[{"type": "refusal", "refusal": "cannot comply"}]),
            LLMErrorCode.REFUSED,
        ),
        (
            response_payload(content=[{"type": "output_text", "text": ""}]),
            LLMErrorCode.INVALID_RESPONSE,
        ),
        ({"unexpected": True}, LLMErrorCode.INVALID_RESPONSE),
    ),
)
async def test_non_usable_provider_outputs_fail_closed(
    payload: dict[str, object], expected_code: LLMErrorCode
) -> None:
    async with adapter_for(lambda _: httpx.Response(200, json=payload)) as adapter:
        with pytest.raises(LLMAdapterError) as raised:
            await adapter.compose(request())

    assert raised.value.code is expected_code


@pytest.mark.asyncio
async def test_api_key_is_absent_from_logs_and_errors(
    caplog: pytest.LogCaptureFixture,
) -> None:
    async with adapter_for(lambda _: httpx.Response(401, json={})) as adapter:
        with pytest.raises(LLMAdapterError) as raised:
            await adapter.compose(request())

    assert TEST_KEY not in caplog.text
    assert TEST_KEY not in str(raised.value)


def test_factory_requires_explicit_provider_model_and_key() -> None:
    with pytest.raises(ValueError):
        create_openai_responses_adapter(Settings())
    with pytest.raises(ValueError):
        create_openai_responses_adapter(
            Settings(llm_provider="other", llm_model="model", llm_api_key=TEST_KEY)
        )
