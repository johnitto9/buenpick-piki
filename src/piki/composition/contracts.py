from enum import StrEnum
from typing import Literal, Protocol

from pydantic import Field

from piki.domain.contracts import ContractModel


class ConversationTurn(ContractModel):
    role: Literal["user", "assistant"]
    text: str = Field(min_length=1, max_length=4096)


class CompositionRequest(ContractModel):
    system_prompt: str = Field(min_length=1, max_length=12000)
    evidence_prompt: str = Field(min_length=1, max_length=30000)
    conversation: tuple[ConversationTurn, ...] = Field(default=(), max_length=20)
    trace_id: str = Field(min_length=1, max_length=128)


class CompositionResult(ContractModel):
    text: str = Field(min_length=1, max_length=4096)
    provider_response_id: str = Field(min_length=1, max_length=255)
    model: str = Field(min_length=1, max_length=255)
    trace_id: str = Field(min_length=1, max_length=128)


class LLMErrorCode(StrEnum):
    BAD_REQUEST = "bad_request"
    UNAUTHORIZED = "unauthorized"
    RATE_LIMITED = "rate_limited"
    TIMEOUT = "timeout"
    UNAVAILABLE = "unavailable"
    REFUSED = "refused"
    INVALID_RESPONSE = "invalid_response"


class LLMAdapterError(Exception):
    def __init__(
        self,
        *,
        code: LLMErrorCode,
        user_safe_message: str,
        status_code: int | None = None,
    ) -> None:
        super().__init__(code.value)
        self.code = code
        self.user_safe_message = user_safe_message
        self.status_code = status_code


class LLMAdapter(Protocol):
    async def compose(self, request: CompositionRequest) -> CompositionResult: ...
