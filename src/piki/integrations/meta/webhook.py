import hashlib
import hmac
from datetime import UTC, datetime
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, SecretStr, ValidationError, model_validator

from piki.domain.contracts import (
    Channel,
    ContractModel,
    DeliveryStatus,
    InboundMessage,
    MessageKind,
)


class MetaWebhookError(ValueError):
    pass


class MetaIngressRetryableError(RuntimeError):
    pass


class MetaPayloadModel(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)


class MetaMetadata(MetaPayloadModel):
    display_phone_number: str
    phone_number_id: str


class MetaText(MetaPayloadModel):
    body: str


class MetaImage(MetaPayloadModel):
    id: str
    mime_type: str | None = None
    sha256: str | None = None
    caption: str | None = None


class MetaReply(MetaPayloadModel):
    id: str
    title: str
    description: str | None = None


class MetaInteractive(MetaPayloadModel):
    type: str
    button_reply: MetaReply | None = None
    list_reply: MetaReply | None = None


class MetaMessage(MetaPayloadModel):
    id: str
    from_: str = Field(alias="from")
    timestamp: str
    type: str
    text: MetaText | None = None
    image: MetaImage | None = None
    interactive: MetaInteractive | None = None


class MetaErrorData(MetaPayloadModel):
    details: str | None = None


class MetaStatusError(MetaPayloadModel):
    code: int
    title: str | None = None
    message: str | None = None
    error_data: MetaErrorData | None = None


class MetaStatus(MetaPayloadModel):
    id: str
    status: Literal["sent", "delivered", "read", "failed"]
    timestamp: str
    recipient_id: str
    errors: tuple[MetaStatusError, ...] = ()


class MetaValue(MetaPayloadModel):
    messaging_product: Literal["whatsapp"]
    metadata: MetaMetadata
    messages: tuple[MetaMessage, ...] = ()
    statuses: tuple[MetaStatus, ...] = ()


class MetaChange(MetaPayloadModel):
    field: Literal["messages"]
    value: MetaValue


class MetaEntry(MetaPayloadModel):
    id: str
    changes: tuple[MetaChange, ...]


class MetaWebhookPayload(MetaPayloadModel):
    object: Literal["whatsapp_business_account"]
    entry: tuple[MetaEntry, ...]


class MetaStatusUpdate(ContractModel):
    provider_message_id: str = Field(min_length=1, max_length=255)
    phone_number_id: str = Field(min_length=1, max_length=255)
    recipient_id: str = Field(min_length=1, max_length=255)
    status: DeliveryStatus
    occurred_at: datetime
    error_code: str | None = Field(default=None, max_length=100)
    error_message: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def validate_error_shape(self) -> "MetaStatusUpdate":
        if self.status is DeliveryStatus.FAILED and self.error_code is None:
            raise ValueError("failed Meta status requires an error code")
        if self.status is not DeliveryStatus.FAILED and self.error_code is not None:
            raise ValueError("non-failed Meta status cannot contain an error code")
        return self


class MetaWebhookEvents(ContractModel):
    messages: tuple[InboundMessage, ...] = ()
    statuses: tuple[MetaStatusUpdate, ...] = ()


class WebhookIngestResult(ContractModel):
    accepted_messages: int = Field(ge=0)
    duplicate_messages: int = Field(ge=0)
    accepted_statuses: int = Field(ge=0)
    duplicate_statuses: int = Field(default=0, ge=0)
    ignored_statuses: int = Field(default=0, ge=0)


class MetaWebhookIngress(Protocol):
    async def ingest(self, events: MetaWebhookEvents) -> WebhookIngestResult: ...


def verify_challenge(
    *, mode: str | None, provided_token: str | None, expected_token: SecretStr
) -> bool:
    if mode != "subscribe" or provided_token is None:
        return False
    return hmac.compare_digest(provided_token, expected_token.get_secret_value())


def verify_signature(raw_body: bytes, signature_header: str | None, app_secret: SecretStr) -> bool:
    if signature_header is None or not signature_header.startswith("sha256="):
        return False
    provided_digest = signature_header.removeprefix("sha256=")
    if len(provided_digest) != 64:
        return False
    expected_digest = hmac.new(
        app_secret.get_secret_value().encode(),
        raw_body,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(provided_digest, expected_digest)


def _timestamp(value: str) -> datetime:
    try:
        return datetime.fromtimestamp(int(value), tz=UTC)
    except (ValueError, OSError) as error:
        raise MetaWebhookError("invalid Meta timestamp") from error


def _message_metadata(
    message: MetaMessage, phone_number_id: str
) -> tuple[MessageKind, str | None, dict[str, str]]:
    metadata = {
        "phone_number_id": phone_number_id,
        "meta_message_type": message.type,
    }
    if message.type == "text" and message.text is not None:
        return MessageKind.TEXT, message.text.body, metadata
    if message.type == "image" and message.image is not None:
        metadata["media_id"] = message.image.id
        if message.image.mime_type:
            metadata["mime_type"] = message.image.mime_type
        if message.image.sha256:
            metadata["media_sha256"] = message.image.sha256
        return MessageKind.IMAGE, message.image.caption, metadata
    if message.type == "interactive" and message.interactive is not None:
        reply = message.interactive.button_reply or message.interactive.list_reply
        if reply is not None:
            metadata["interaction_id"] = reply.id
            metadata["interaction_type"] = message.interactive.type
            return MessageKind.INTERACTIVE, reply.title, metadata
    return MessageKind.UNSUPPORTED, None, metadata


def normalize_webhook(
    payload: dict[str, Any],
    *,
    expected_waba_id: str | None = None,
    expected_phone_number_id: str | None = None,
) -> MetaWebhookEvents:
    try:
        parsed = MetaWebhookPayload.model_validate(payload)
    except ValidationError as validation_error:
        raise MetaWebhookError("invalid Meta webhook payload") from validation_error

    messages: list[InboundMessage] = []
    statuses: list[MetaStatusUpdate] = []
    status_map = {
        "sent": DeliveryStatus.SENT,
        "delivered": DeliveryStatus.DELIVERED,
        "read": DeliveryStatus.READ,
        "failed": DeliveryStatus.FAILED,
    }
    for entry in parsed.entry:
        if expected_waba_id is not None and entry.id != expected_waba_id:
            raise MetaWebhookError("unexpected Meta WABA ID")
        for change in entry.changes:
            phone_number_id = change.value.metadata.phone_number_id
            if (
                expected_phone_number_id is not None
                and phone_number_id != expected_phone_number_id
            ):
                raise MetaWebhookError("unexpected Meta phone number ID")
            for message in change.value.messages:
                kind, text, metadata = _message_metadata(message, phone_number_id)
                try:
                    messages.append(
                        InboundMessage(
                            message_id=message.id,
                            channel=Channel.WHATSAPP,
                            conversation_id=message.from_,
                            sender_id=message.from_,
                            kind=kind,
                            text=text,
                            received_at=_timestamp(message.timestamp),
                            metadata=metadata,
                        )
                    )
                except ValidationError as validation_error:
                    raise MetaWebhookError(
                        "invalid normalized Meta message"
                    ) from validation_error
            for status in change.value.statuses:
                status_error = status.errors[0] if status.errors else None
                error_message = None
                if status_error is not None:
                    error_message = (
                        status_error.error_data.details
                        if status_error.error_data and status_error.error_data.details
                        else status_error.message or status_error.title
                    )
                try:
                    statuses.append(
                        MetaStatusUpdate(
                            provider_message_id=status.id,
                            phone_number_id=phone_number_id,
                            recipient_id=status.recipient_id,
                            status=status_map[status.status],
                            occurred_at=_timestamp(status.timestamp),
                            error_code=str(status_error.code) if status_error else None,
                            error_message=error_message,
                        )
                    )
                except ValidationError as validation_error:
                    raise MetaWebhookError(
                        "invalid normalized Meta status"
                    ) from validation_error
    return MetaWebhookEvents(messages=tuple(messages), statuses=tuple(statuses))
