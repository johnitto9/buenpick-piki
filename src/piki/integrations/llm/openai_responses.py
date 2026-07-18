import asyncio
from collections.abc import Awaitable, Callable
from typing import Literal

import httpx
from pydantic import BaseModel, ConfigDict, SecretStr, ValidationError

from piki.composition.contracts import (
    CompositionRequest,
    CompositionResult,
    LLMAdapterError,
    LLMErrorCode,
)
from piki.core.config import Settings

Sleep = Callable[[float], Awaitable[None]]


class ProviderModel(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)


class OutputContent(ProviderModel):
    type: Literal["output_text", "refusal"]
    text: str | None = None
    refusal: str | None = None


class OutputItem(ProviderModel):
    type: str
    content: tuple[OutputContent, ...] = ()


class ResponsesEnvelope(ProviderModel):
    id: str
    model: str
    status: str
    output: tuple[OutputItem, ...]


class OpenAIResponsesAdapter:
    def __init__(
        self,
        *,
        base_url: str,
        api_key: SecretStr,
        model: str,
        timeout_seconds: float = 15.0,
        max_attempts: int = 2,
        max_output_tokens: int = 500,
        transport: httpx.AsyncBaseTransport | None = None,
        sleep: Sleep = asyncio.sleep,
    ) -> None:
        if not api_key.get_secret_value().strip():
            raise ValueError("LLM API key is required")
        if not model.strip():
            raise ValueError("LLM model is required")
        if max_attempts < 1:
            raise ValueError("LLM max_attempts must be positive")
        self._model = model.strip()
        self._max_attempts = max_attempts
        self._max_output_tokens = max_output_tokens
        self._sleep = sleep
        self._client = httpx.AsyncClient(
            base_url=f"{base_url.rstrip('/')}/",
            headers={
                "Authorization": f"Bearer {api_key.get_secret_value()}",
                "Content-Type": "application/json",
                "User-Agent": "piki/0.1",
            },
            timeout=httpx.Timeout(timeout_seconds),
            transport=transport,
        )

    async def __aenter__(self) -> "OpenAIResponsesAdapter":
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.close()

    async def close(self) -> None:
        await self._client.aclose()

    async def compose(self, request: CompositionRequest) -> CompositionResult:
        input_messages = [
            {"role": turn.role, "content": turn.text} for turn in request.conversation
        ]
        input_messages.append(
            {
                "role": "user",
                "content": (
                    "Redactá la respuesta final usando exclusivamente "
                    "este paquete de evidencia:\n\n"
                    f"{request.evidence_prompt}"
                ),
            }
        )
        body = {
            "model": self._model,
            "instructions": request.system_prompt,
            "input": input_messages,
            "max_output_tokens": self._max_output_tokens,
            "store": False,
        }

        for attempt in range(1, self._max_attempts + 1):
            try:
                response = await self._client.post("responses", json=body)
            except httpx.TimeoutException as error:
                if attempt < self._max_attempts:
                    await self._sleep(0.2 * attempt)
                    continue
                raise LLMAdapterError(
                    code=LLMErrorCode.TIMEOUT,
                    user_safe_message="No pude redactar la respuesta a tiempo.",
                ) from error
            except httpx.RequestError as error:
                raise LLMAdapterError(
                    code=LLMErrorCode.UNAVAILABLE,
                    user_safe_message="No pude acceder al redactor en este momento.",
                ) from error

            if response.status_code in {429, 500, 502, 503} and attempt < self._max_attempts:
                await self._sleep(0.2 * attempt)
                continue
            if response.is_error:
                raise self._map_http_error(response.status_code)
            return self._parse_response(response, request.trace_id)

        raise AssertionError("LLM request loop exhausted unexpectedly")

    @staticmethod
    def _parse_response(response: httpx.Response, trace_id: str) -> CompositionResult:
        try:
            envelope = ResponsesEnvelope.model_validate(response.json())
        except (ValueError, ValidationError) as error:
            raise LLMAdapterError(
                code=LLMErrorCode.INVALID_RESPONSE,
                user_safe_message="El redactor devolvió una respuesta inválida.",
            ) from error
        if envelope.status != "completed":
            raise LLMAdapterError(
                code=LLMErrorCode.INVALID_RESPONSE,
                user_safe_message="El redactor no completó la respuesta.",
            )

        text_parts: list[str] = []
        refused = False
        for item in envelope.output:
            if item.type != "message":
                continue
            for content in item.content:
                if content.type == "refusal":
                    refused = True
                elif content.type == "output_text" and content.text:
                    text_parts.append(content.text.strip())
        if refused:
            raise LLMAdapterError(
                code=LLMErrorCode.REFUSED,
                user_safe_message="No pude redactar esa respuesta.",
            )
        text = "\n".join(part for part in text_parts if part).strip()
        if not text:
            raise LLMAdapterError(
                code=LLMErrorCode.INVALID_RESPONSE,
                user_safe_message="El redactor no devolvió texto utilizable.",
            )
        return CompositionResult(
            text=text,
            provider_response_id=envelope.id,
            model=envelope.model,
            trace_id=trace_id,
        )

    @staticmethod
    def _map_http_error(status_code: int) -> LLMAdapterError:
        if status_code == 400:
            code = LLMErrorCode.BAD_REQUEST
        elif status_code == 401:
            code = LLMErrorCode.UNAUTHORIZED
        elif status_code == 429:
            code = LLMErrorCode.RATE_LIMITED
        else:
            code = LLMErrorCode.UNAVAILABLE
        return LLMAdapterError(
            code=code,
            user_safe_message="No pude redactar la respuesta en este momento.",
            status_code=status_code,
        )


def create_openai_responses_adapter(
    settings: Settings,
    *,
    transport: httpx.AsyncBaseTransport | None = None,
    sleep: Sleep = asyncio.sleep,
) -> OpenAIResponsesAdapter:
    if settings.llm_provider != "openai":
        raise ValueError("only the openai LLM provider is currently implemented")
    api_key = settings.resolved_llm_api_key
    if api_key is None:
        raise ValueError("LLM API key is required")
    if settings.llm_model is None:
        raise ValueError("LLM model is required")
    return OpenAIResponsesAdapter(
        base_url=settings.llm_base_url,
        api_key=api_key,
        model=settings.llm_model,
        timeout_seconds=settings.llm_timeout_seconds,
        max_attempts=settings.llm_max_attempts,
        max_output_tokens=settings.llm_max_output_tokens,
        transport=transport,
        sleep=sleep,
    )
