from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from piki.domain.contracts import (
    Channel,
    ContextPacket,
    DeliveryKind,
    DeliveryRequest,
    DeliveryResult,
    DeliveryStatus,
    EvidenceItem,
    EvidenceSource,
    InboundMessage,
    MessageKind,
    ResponseMode,
    ToolErrorCode,
    ToolResult,
)


def test_normalized_message_requires_text_and_timezone() -> None:
    message = InboundMessage(
        message_id="wamid.test",
        channel=Channel.WHATSAPP,
        conversation_id="conversation-test",
        sender_id="sender-test",
        kind=MessageKind.TEXT,
        text="Quiero ver picks para retirar hoy",
        received_at=datetime.now(UTC),
    )
    assert message.schema_version == "1.0"

    with pytest.raises(ValidationError):
        InboundMessage(
            message_id="wamid.empty",
            channel=Channel.WHATSAPP,
            conversation_id="conversation-test",
            sender_id="sender-test",
            kind=MessageKind.TEXT,
            received_at=datetime.now(UTC),
        )


def test_tool_failure_cannot_hide_its_error() -> None:
    with pytest.raises(ValidationError):
        ToolResult[dict[str, str]](
            success=False,
            latency_ms=20,
            trace_id="trace-test",
        )

    result = ToolResult[dict[str, str]](
        success=False,
        error_code=ToolErrorCode.UPSTREAM_UNAVAILABLE,
        user_safe_message="No pude confirmar los picks disponibles en este momento.",
        latency_ms=20,
        trace_id="trace-test",
    )
    assert result.success is False


def test_context_packet_keeps_confirmed_data_and_voice_rules_separate() -> None:
    packet = ContextPacket(
        task="Explain one currently available rescue pick",
        query="Que puedo rescatar hoy?",
        confirmed_data=(
            EvidenceItem(
                label="pick_title",
                value="Anonymous rescue pick",
                source=EvidenceSource.BUENPICK_INTERNAL_API,
                source_reference="pick-fixture",
            ),
        ),
        writing_rules=(
            "Speak as Piki, BuenPick's practical and warm rescue-market assistant.",
            "Do not invent the exact contents of a surprise bag.",
        ),
        response_mode=ResponseMode.JINJA_LLM,
        active_pick_id="pick-fixture",
        trace_id="trace-test",
    )
    assert packet.confirmed_data[0].source is EvidenceSource.BUENPICK_INTERNAL_API
    assert "Piki" in packet.writing_rules[0]


def test_delivery_failure_cannot_be_reported_as_success() -> None:
    failure = DeliveryResult(
        status=DeliveryStatus.FAILED,
        error_code="meta_rejected",
        error_message="Provider rejected the request",
        trace_id="trace-test",
    )
    assert failure.status is DeliveryStatus.FAILED

    with pytest.raises(ValidationError):
        DeliveryResult(
            status=DeliveryStatus.DELIVERED,
            error_code="meta_rejected",
            trace_id="trace-test",
        )

    unknown = DeliveryResult(
        status=DeliveryStatus.UNKNOWN,
        error_code="provider_result_uncertain",
        trace_id="trace-test",
    )
    assert unknown.status is DeliveryStatus.UNKNOWN

    with pytest.raises(ValidationError, match="requires a message ID"):
        DeliveryResult(
            status=DeliveryStatus.ACCEPTED,
            trace_id="trace-test",
        )


def test_image_delivery_requires_an_http_media_url() -> None:
    with pytest.raises(ValidationError):
        DeliveryRequest(
            idempotency_key="delivery-test",
            conversation_id="conversation-test",
            kind=DeliveryKind.IMAGE,
            trace_id="trace-test",
        )

    request = DeliveryRequest(
        idempotency_key="delivery-test",
        conversation_id="conversation-test",
        kind=DeliveryKind.IMAGE,
        media_url="https://fixtures.invalid/pick.jpg",
        trace_id="trace-test",
    )
    assert str(request.media_url).startswith("https://")
