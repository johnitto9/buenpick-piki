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
from piki.integrations.llm.openai_chat import OpenAIChatCompletionsAdapter

Handler = Callable[[httpx.Request], httpx.Response]
TEST_KEY = "nvidia-nim-contract-test-key"


def request() -> CompositionRequest:
    return CompositionRequest(
        system_prompt="Sos Piki y usás sólo evidencia confirmada.",
        evidence_prompt="DATOS CONFIRMADOS\n- rescate disponible",
        conversation=(ConversationTurn(role="user", text="Hola Piki"),),
        trace_id="trace-nim",
    )


def payload(content: str = "Hola, soy Piki.") -> dict[str, object]:
    return {
        "id": "chatcmpl-test-1",
        "model": "z-ai/glm-5.2",
        "choices": [{"message": {"role": "assistant", "content": content}}],
    }


async def no_sleep(_: float) -> None:
    return None


def adapter(handler: Handler, *, attempts: int = 2) -> OpenAIChatCompletionsAdapter:
    return OpenAIChatCompletionsAdapter(
        base_url="https://nim.mock.invalid/v1",
        api_key=SecretStr(TEST_KEY),
        model="z-ai/glm-5.2",
        max_attempts=attempts,
        transport=httpx.MockTransport(handler),
        sleep=no_sleep,
    )


@pytest.mark.asyncio
async def test_chat_request_separates_system_history_and_evidence() -> None:
    observed: list[httpx.Request] = []

    def handler(http_request: httpx.Request) -> httpx.Response:
        observed.append(http_request)
        return httpx.Response(200, json=payload())

    client = adapter(handler)
    try:
        result = await client.compose(request())
    finally:
        await client.close()

    body = json.loads(observed[0].content)
    assert observed[0].url.path == "/v1/chat/completions"
    assert observed[0].headers["Authorization"] == f"Bearer {TEST_KEY}"
    assert body["model"] == "z-ai/glm-5.2"
    assert body["messages"][0] == {
        "role": "system",
        "content": request().system_prompt,
    }
    assert body["messages"][1]["role"] == "user"
    assert "Hola Piki" in body["messages"][1]["content"]
    assert request().evidence_prompt in body["messages"][1]["content"]
    assert len(body["messages"]) == 2
    assert body["stream"] is False
    assert result.text == "Hola, soy Piki."
    assert result.provider_response_id == "chatcmpl-test-1"


@pytest.mark.asyncio
async def test_chat_timeout_and_invalid_payload_fail_closed() -> None:
    def timeout(http_request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("private timeout", request=http_request)

    timeout_client = adapter(timeout, attempts=1)
    try:
        with pytest.raises(LLMAdapterError) as raised:
            await timeout_client.compose(request())
    finally:
        await timeout_client.close()
    assert raised.value.code is LLMErrorCode.TIMEOUT
    assert "private timeout" not in str(raised.value)

    invalid_client = adapter(lambda _: httpx.Response(200, json={}))
    try:
        with pytest.raises(LLMAdapterError) as invalid:
            await invalid_client.compose(request())
    finally:
        await invalid_client.close()
    assert invalid.value.code is LLMErrorCode.INVALID_RESPONSE


@pytest.mark.asyncio
async def test_chat_provider_error_does_not_leak_key_or_body(
    caplog: pytest.LogCaptureFixture,
) -> None:
    client = adapter(
        lambda _: httpx.Response(
            401,
            json={"error": {"message": "private provider rejection"}},
        ),
        attempts=1,
    )
    try:
        with pytest.raises(LLMAdapterError) as raised:
            await client.compose(request())
    finally:
        await client.close()
    assert raised.value.code is LLMErrorCode.UNAUTHORIZED
    assert TEST_KEY not in caplog.text
    assert "private provider rejection" not in str(raised.value)
