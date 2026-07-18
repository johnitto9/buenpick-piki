from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Channel(StrEnum):
    WHATSAPP = "whatsapp"
    WEB = "web"


class MessageKind(StrEnum):
    TEXT = "text"
    IMAGE = "image"
    INTERACTIVE = "interactive"
    UNSUPPORTED = "unsupported"


class InboundMessage(ContractModel):
    schema_version: Literal["1.0"] = "1.0"
    message_id: str = Field(min_length=1, max_length=255)
    channel: Channel
    conversation_id: str = Field(min_length=1, max_length=255)
    sender_id: str = Field(min_length=1, max_length=255)
    kind: MessageKind
    text: str | None = Field(default=None, max_length=4096)
    received_at: datetime
    metadata: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_text_message(self) -> "InboundMessage":
        if self.received_at.tzinfo is None:
            raise ValueError("received_at must include a timezone")
        if self.kind is MessageKind.TEXT and not (self.text and self.text.strip()):
            raise ValueError("text messages require non-empty text")
        return self


class ToolErrorCode(StrEnum):
    BAD_REQUEST = "bad_request"
    UNAUTHORIZED = "unauthorized"
    NOT_FOUND = "not_found"
    RATE_LIMITED = "rate_limited"
    TIMEOUT = "timeout"
    UPSTREAM_UNAVAILABLE = "upstream_unavailable"
    INTERNAL_ERROR = "internal_error"


class ToolResult[DataT](ContractModel):
    schema_version: Literal["1.0"] = "1.0"
    success: bool
    data: DataT | None = None
    error_code: ToolErrorCode | None = None
    user_safe_message: str | None = Field(default=None, max_length=500)
    latency_ms: int = Field(ge=0)
    trace_id: str = Field(min_length=1, max_length=128)

    @model_validator(mode="after")
    def validate_result_shape(self) -> "ToolResult[DataT]":
        if self.success and self.error_code is not None:
            raise ValueError("successful tool results cannot contain an error code")
        if not self.success and self.error_code is None:
            raise ValueError("failed tool results require an error code")
        if not self.success and not self.user_safe_message:
            raise ValueError("failed tool results require a user-safe message")
        return self


class EvidenceSource(StrEnum):
    BUENPICK_INTERNAL_API = "buenpick_internal_api"
    CONVERSATION = "conversation"
    POLICY = "policy"


class EvidenceItem(ContractModel):
    label: str = Field(min_length=1, max_length=100)
    value: str = Field(min_length=1, max_length=2000)
    source: EvidenceSource
    source_reference: str | None = Field(default=None, max_length=255)


class PerformedAction(ContractModel):
    name: str = Field(min_length=1, max_length=100)
    outcome: Literal["succeeded", "failed", "skipped"]
    reference: str | None = Field(default=None, max_length=255)


class ResponseMode(StrEnum):
    DETERMINISTIC = "deterministic"
    JINJA = "jinja"
    JINJA_LLM = "jinja_llm"
    NON_COMMERCIAL_LLM = "non_commercial_llm"


class ContextPacket(ContractModel):
    schema_version: Literal["1.0"] = "1.0"
    task: str = Field(min_length=1, max_length=500)
    query: str = Field(min_length=1, max_length=4096)
    confirmed_data: tuple[EvidenceItem, ...] = ()
    unavailable_data: tuple[str, ...] = ()
    actions_performed: tuple[PerformedAction, ...] = ()
    writing_rules: tuple[str, ...] = ()
    response_mode: ResponseMode
    active_pick_id: str | None = Field(default=None, max_length=255)
    trace_id: str = Field(min_length=1, max_length=128)


class DeliveryKind(StrEnum):
    TEXT = "text"
    IMAGE = "image"
    INTERACTIVE = "interactive"
    TEMPLATE = "template"


class CustomerServiceWindow(StrEnum):
    OPEN = "open"
    CLOSED = "closed"
    UNKNOWN = "unknown"


class InteractiveOption(ContractModel):
    id: str = Field(min_length=1, max_length=256)
    title: str = Field(min_length=1, max_length=20)


class DeliveryRequest(ContractModel):
    schema_version: Literal["1.0"] = "1.0"
    idempotency_key: str = Field(min_length=1, max_length=255)
    conversation_id: str = Field(min_length=1, max_length=255)
    kind: DeliveryKind
    text: str | None = Field(default=None, max_length=4096)
    media_url: HttpUrl | None = None
    interactive_options: tuple[InteractiveOption, ...] = Field(default=(), max_length=3)
    template_name: str | None = Field(default=None, min_length=1, max_length=512)
    template_language: str | None = Field(default=None, min_length=2, max_length=35)
    template_parameters: tuple[str, ...] = Field(default=(), max_length=10)
    customer_service_window: CustomerServiceWindow = CustomerServiceWindow.UNKNOWN
    trace_id: str = Field(min_length=1, max_length=128)

    @model_validator(mode="after")
    def validate_content(self) -> "DeliveryRequest":
        if self.kind is DeliveryKind.TEXT and not self.text:
            raise ValueError("text delivery requires text")
        if self.kind is DeliveryKind.IMAGE and self.media_url is None:
            raise ValueError("image delivery requires media_url")
        if self.kind is DeliveryKind.INTERACTIVE and (
            not self.text or not self.interactive_options
        ):
            raise ValueError("interactive delivery requires text and options")
        if self.kind is DeliveryKind.TEMPLATE and (
            self.template_name is None or self.template_language is None
        ):
            raise ValueError("template delivery requires name and language")
        if self.kind is not DeliveryKind.INTERACTIVE and self.interactive_options:
            raise ValueError("interactive options require interactive delivery")
        if self.kind is not DeliveryKind.TEMPLATE and (
            self.template_name or self.template_language or self.template_parameters
        ):
            raise ValueError("template fields require template delivery")
        return self


class DeliveryStatus(StrEnum):
    UNKNOWN = "unknown"
    ACCEPTED = "accepted"
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"
    FAILED = "failed"


class DeliveryResult(ContractModel):
    schema_version: Literal["1.0"] = "1.0"
    status: DeliveryStatus
    provider_message_id: str | None = Field(default=None, max_length=255)
    error_code: str | None = Field(default=None, max_length=100)
    error_message: str | None = Field(default=None, max_length=500)
    trace_id: str = Field(min_length=1, max_length=128)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_delivery_truth(self) -> "DeliveryResult":
        error_statuses = {DeliveryStatus.FAILED, DeliveryStatus.UNKNOWN}
        provider_statuses = {
            DeliveryStatus.ACCEPTED,
            DeliveryStatus.SENT,
            DeliveryStatus.DELIVERED,
            DeliveryStatus.READ,
        }
        if self.status in error_statuses and not self.error_code:
            raise ValueError("failed or unknown delivery requires an error code")
        if self.status not in error_statuses and self.error_code is not None:
            raise ValueError("successful delivery status cannot contain an error code")
        if self.status in provider_statuses and not self.provider_message_id:
            raise ValueError("provider delivery status requires a message ID")
        return self
