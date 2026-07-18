import hashlib
import hmac
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from piki.api.app import create_app
from piki.core.config import Environment, Settings
from piki.domain.contracts import DeliveryStatus, MessageKind
from piki.integrations.meta.webhook import (
    MetaWebhookError,
    MetaWebhookEvents,
    WebhookIngestResult,
    normalize_webhook,
    verify_signature,
)

FIXTURES = Path(__file__).parents[1] / "fixtures" / "meta"
VERIFY_TOKEN = "meta-verify-test-token"  # noqa: S105 - inert fixture credential
APP_SECRET = "meta-app-test-secret"  # noqa: S105 - inert fixture credential
WABA_ID = "waba-test-1"
PHONE_NUMBER_ID = "phone-number-test-1"


def load_fixture(name: str) -> dict[str, object]:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def signature(body: bytes) -> str:
    digest = hmac.new(APP_SECRET.encode(), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


class StubReadiness:
    async def check(self) -> object:
        raise AssertionError("webhook tests must not call readiness")

    async def close(self) -> None:
        return None


class RecordingIngress:
    def __init__(self) -> None:
        self.events: list[MetaWebhookEvents] = []

    async def ingest(self, events: MetaWebhookEvents) -> WebhookIngestResult:
        self.events.append(events)
        return WebhookIngestResult(
            accepted_messages=len(events.messages),
            duplicate_messages=0,
            accepted_statuses=len(events.statuses),
        )


def webhook_client(ingress: RecordingIngress | None = None) -> TestClient:
    settings = Settings(
        environment=Environment.TEST,
        meta_webhook_verify_token=VERIFY_TOKEN,
        meta_app_secret=APP_SECRET,
        meta_waba_id=WABA_ID,
        meta_phone_number_id=PHONE_NUMBER_ID,
    )
    return TestClient(
        create_app(
            settings=settings,
            readiness=StubReadiness(),  # type: ignore[arg-type]
            meta_ingress=ingress,
        )
    )


def test_challenge_requires_exact_verify_token() -> None:
    with webhook_client(RecordingIngress()) as client:
        accepted = client.get(
            "/webhooks/meta/whatsapp",
            params={
                "hub.mode": "subscribe",
                "hub.verify_token": VERIFY_TOKEN,
                "hub.challenge": "challenge-123",
            },
        )
        rejected = client.get(
            "/webhooks/meta/whatsapp",
            params={
                "hub.mode": "subscribe",
                "hub.verify_token": "wrong-token",
                "hub.challenge": "challenge-123",
            },
        )
        wrong_mode = client.get(
            "/webhooks/meta/whatsapp",
            params={
                "hub.mode": "unexpected",
                "hub.verify_token": VERIFY_TOKEN,
                "hub.challenge": "challenge-123",
            },
        )

    assert accepted.status_code == 200
    assert accepted.text == "challenge-123"
    assert accepted.headers["content-type"].startswith("text/plain")
    assert rejected.status_code == 403
    assert wrong_mode.status_code == 403


def test_valid_signature_is_normalized_before_ingress_acknowledgement() -> None:
    ingress = RecordingIngress()
    raw_body = (FIXTURES / "inbound_messages.json").read_bytes()

    with webhook_client(ingress) as client:
        response = client.post(
            "/webhooks/meta/whatsapp",
            content=raw_body,
            headers={
                "Content-Type": "application/json",
                "X-Hub-Signature-256": signature(raw_body),
            },
        )

    assert response.status_code == 200
    assert response.json() == {
        "accepted_messages": 4,
        "duplicate_messages": 0,
        "accepted_statuses": 0,
        "duplicate_statuses": 0,
        "ignored_statuses": 0,
    }
    assert len(ingress.events) == 1
    assert [message.kind for message in ingress.events[0].messages] == [
        MessageKind.TEXT,
        MessageKind.IMAGE,
        MessageKind.INTERACTIVE,
        MessageKind.UNSUPPORTED,
    ]


def test_invalid_signature_is_rejected_without_calling_ingress() -> None:
    ingress = RecordingIngress()
    raw_body = (FIXTURES / "inbound_messages.json").read_bytes()

    with webhook_client(ingress) as client:
        response = client.post(
            "/webhooks/meta/whatsapp",
            content=raw_body,
            headers={"X-Hub-Signature-256": "sha256=" + "0" * 64},
        )

    assert response.status_code == 401
    assert ingress.events == []


def test_signature_for_original_body_rejects_an_altered_http_body() -> None:
    ingress = RecordingIngress()
    raw_body = (FIXTURES / "inbound_messages.json").read_bytes()

    with webhook_client(ingress) as client:
        response = client.post(
            "/webhooks/meta/whatsapp",
            content=raw_body + b"\n",
            headers={"X-Hub-Signature-256": signature(raw_body)},
        )

    assert response.status_code == 401
    assert ingress.events == []


@pytest.mark.parametrize("destination", ["waba", "phone"])
def test_signed_event_for_an_unconfigured_meta_asset_is_rejected(
    destination: str,
) -> None:
    ingress = RecordingIngress()
    payload = load_fixture("inbound_messages.json")
    if destination == "waba":
        payload["entry"][0]["id"] = "waba-not-configured"  # type: ignore[index]
    else:
        payload["entry"][0]["changes"][0]["value"]["metadata"][  # type: ignore[index]
            "phone_number_id"
        ] = "phone-not-configured"
    raw_body = json.dumps(payload, separators=(",", ":")).encode()

    with webhook_client(ingress) as client:
        response = client.post(
            "/webhooks/meta/whatsapp",
            content=raw_body,
            headers={"X-Hub-Signature-256": signature(raw_body)},
        )

    assert response.status_code == 400
    assert ingress.events == []


def test_valid_event_is_not_acknowledged_without_real_ingress() -> None:
    raw_body = (FIXTURES / "inbound_messages.json").read_bytes()

    with webhook_client() as client:
        response = client.post(
            "/webhooks/meta/whatsapp",
            content=raw_body,
            headers={"X-Hub-Signature-256": signature(raw_body)},
        )

    assert response.status_code == 503


def test_text_image_interactive_and_unsupported_messages_are_normalized() -> None:
    events = normalize_webhook(load_fixture("inbound_messages.json"))

    assert len(events.messages) == 4
    text, image, interactive, unsupported = events.messages
    assert text.text == "Hola Piki, ¿qué puedo rescatar hoy?"
    assert text.conversation_id == "5492914000000"
    assert text.metadata["phone_number_id"] == "phone-number-test-1"
    assert image.text == "¿Es este pick?"
    assert image.metadata["media_id"] == "media-test-1"
    assert interactive.text == "Ver este pick"
    assert interactive.metadata["interaction_id"] == "view-pick-test-1"
    assert unsupported.kind is MessageKind.UNSUPPORTED
    assert unsupported.text is None


@pytest.mark.parametrize("message_type", ["audio", "document", "video", "sticker"])
def test_unimplemented_media_is_safely_normalized_as_unsupported(
    message_type: str,
) -> None:
    payload = load_fixture("inbound_messages.json")
    messages = payload["entry"][0]["changes"][0]["value"]["messages"]  # type: ignore[index]
    message = messages[0]  # type: ignore[index]
    message.pop("text")
    message["type"] = message_type
    message[message_type] = {"id": f"media-{message_type}-test"}
    payload["entry"][0]["changes"][0]["value"]["messages"] = [message]  # type: ignore[index]

    events = normalize_webhook(
        payload,
        expected_waba_id=WABA_ID,
        expected_phone_number_id=PHONE_NUMBER_ID,
    )

    assert len(events.messages) == 1
    assert events.messages[0].kind is MessageKind.UNSUPPORTED
    assert events.messages[0].text is None
    assert events.messages[0].metadata["meta_message_type"] == message_type


def test_sent_delivered_read_and_failed_statuses_are_distinct() -> None:
    events = normalize_webhook(load_fixture("status_updates.json"))

    assert [update.status for update in events.statuses] == [
        DeliveryStatus.SENT,
        DeliveryStatus.DELIVERED,
        DeliveryStatus.READ,
        DeliveryStatus.FAILED,
    ]
    failed = events.statuses[-1]
    assert failed.error_code == "131047"
    assert failed.error_message == "Fixture delivery rejection"
    assert events.messages == ()


def test_malformed_payload_and_failed_status_without_error_are_rejected() -> None:
    with pytest.raises(MetaWebhookError):
        normalize_webhook({"object": "unexpected", "entry": []})

    payload = load_fixture("status_updates.json")
    status = payload["entry"][0]["changes"][0]["value"]["statuses"][-1]  # type: ignore[index]
    status["errors"] = []  # type: ignore[index]
    with pytest.raises(MetaWebhookError):
        normalize_webhook(payload)


def test_signature_validation_uses_exact_raw_bytes() -> None:
    body = b'{"object":"whatsapp_business_account","entry":[]}'
    valid = signature(body)

    assert verify_signature(body, valid, SecretStr(APP_SECRET)) is True
    assert verify_signature(body + b"\n", valid, SecretStr(APP_SECRET)) is False
    assert verify_signature(body, "sha256=short", SecretStr(APP_SECRET)) is False
