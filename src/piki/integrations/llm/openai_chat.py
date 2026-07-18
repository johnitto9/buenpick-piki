import asyncio
from collections.abc import Awaitable, Callable

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


class ChatMessage(ProviderModel):
    content: str | None = None


class ChatChoice(ProviderModel):
    message: ChatMessage


class ChatCompletionEnvelope(ProviderModel):
    id: str
    model: str
    choices: tuple[ChatChoice, ...]


class OpenAIChatCompletionsAdapter:
    """Adapter for OpenAI-compatible chat-completions providers such as NVIDIA NIM."""

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

    async def close(self) -> None:
        await self._client.aclose()

    async def compose(self, request: CompositionRequest) -> CompositionResult:
        messages = [{"role": "system", "content": request.system_prompt}]
        for turn in request.conversation:
            self._append_message(messages, turn.role, turn.text)
        self._append_message(
            messages,
            "user",
            (
                "Redactá la respuesta final usando exclusivamente "
                "este paquete de evidencia:\n\n"
                f"{request.evidence_prompt}"
            ),
        )
        body = {
            "model": self._model,
            "messages": messages,
            "temperature": 0.2,
            "top_p": 0.9,
            "max_tokens": self._max_output_tokens,
            "stream": False,
        }

        for attempt in range(1, self._max_attempts + 1):
            try:
                response = await self._client.post("chat/completions", json=body)
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
    def _append_message(
        messages: list[dict[str, str]], role: str, content: str
    ) -> None:
        if messages[-1]["role"] == role:
            messages[-1]["content"] = f"{messages[-1]['content']}\n\n{content}"
            return
        messages.append({"role": role, "content": content})

    @staticmethod
    def _parse_response(response: httpx.Response, trace_id: str) -> CompositionResult:
        try:
            envelope = ChatCompletionEnvelope.model_validate(response.json())
            text = envelope.choices[0].message.content
        except (ValueError, ValidationError, IndexError) as error:
            raise LLMAdapterError(
                code=LLMErrorCode.INVALID_RESPONSE,
                user_safe_message="El redactor devolvió una respuesta inválida.",
            ) from error
        if text is None or not text.strip():
            raise LLMAdapterError(
                code=LLMErrorCode.INVALID_RESPONSE,
                user_safe_message="El redactor no devolvió texto utilizable.",
            )
        return CompositionResult(
            text=text.strip(),
            provider_response_id=envelope.id,
            model=envelope.model,
            trace_id=trace_id,
        )

    @staticmethod
    def _map_http_error(status_code: int) -> LLMAdapterError:
        if status_code == 400:
            code = LLMErrorCode.BAD_REQUEST
        elif status_code in {401, 403}:
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


def create_openai_chat_adapter(
    settings: Settings,
    *,
    transport: httpx.AsyncBaseTransport | None = None,
    sleep: Sleep = asyncio.sleep,
) -> OpenAIChatCompletionsAdapter:
    if settings.llm_provider not in {"nvidia_nim", "openai_chat"}:
        raise ValueError("LLM provider does not use chat completions")
    api_key = settings.resolved_llm_api_key
    if api_key is None:
        raise ValueError("LLM API key is required")
    if settings.llm_model is None:
        raise ValueError("LLM model is required")
    return OpenAIChatCompletionsAdapter(
        base_url=settings.llm_base_url,
        api_key=api_key,
        model=settings.llm_model,
        timeout_seconds=settings.llm_timeout_seconds,
        max_attempts=settings.llm_max_attempts,
        max_output_tokens=settings.llm_max_output_tokens,
        transport=transport,
        sleep=sleep,
    )
