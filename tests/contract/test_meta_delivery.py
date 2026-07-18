import json
from collections.abc import Callable

import httpx
import pytest
from pydantic import SecretStr

from piki.core.config import Settings
from piki.domain.contracts import (
    CustomerServiceWindow,
    DeliveryKind,
    DeliveryRequest,
    DeliveryStatus,
    InteractiveOption,
)
from piki.integrations.meta.delivery import (
    MetaDeliveryAdapter,
    create_meta_delivery_adapter,
)

Handler = Callable[[httpx.Request], httpx.Response]
TEST_TOKEN = "meta-delivery-test-token"  # noqa: S105 - inert fixture credential


def accepted_payload() -> dict[str, object]:
    return {
        "messaging_product": "whatsapp",
        "contacts": [{"input": "5492914000000", "wa_id": "5492914000000"}],
        "messages": [{"id": "wamid.outbound.accepted.1"}],
    }


def request_for(kind: DeliveryKind, **changes: object) -> DeliveryRequest:
    values: dict[str, object] = {
        "idempotency_key": f"delivery-{kind.value}-1",
        "conversation_id": "5492914000000",
        "kind": kind,
        "customer_service_window": CustomerServiceWindow.OPEN,
        "trace_id": f"trace-{kind.value}",
    }
    values.update(changes)
    return DeliveryRequest.model_validate(values)


def adapter_for(handler: Handler) -> MetaDeliveryAdapter:
    return MetaDeliveryAdapter(
        graph_base_url="https://graph.mock.invalid",
        graph_api_version="v-test",
        phone_number_id="phone-number-test-1",
        access_token=SecretStr(TEST_TOKEN),
        transport=httpx.MockTransport(handler),
    )


@pytest.mark.asyncio
async def test_text_delivery_returns_accepted_not_delivered() -> None:
    observed: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        observed.append(request)
        return httpx.Response(200, json=accepted_payload())

    async with adapter_for(handler) as adapter:
        result = await adapter.send(
            request_for(DeliveryKind.TEXT, text="Hay un pick confirmado para rescatar.")
        )

    body = json.loads(observed[0].content)
    assert observed[0].url.path == "/v-test/phone-number-test-1/messages"
    assert observed[0].headers["Authorization"] == f"Bearer {TEST_TOKEN}"
    assert body == {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": "5492914000000",
        "type": "text",
        "text": {
            "preview_url": False,
            "body": "Hay un pick confirmado para rescatar.",
        },
    }
    assert result.status is DeliveryStatus.ACCEPTED
    assert result.provider_message_id == "wamid.outbound.accepted.1"


@pytest.mark.asyncio
async def test_image_delivery_uses_confirmed_public_link_and_caption() -> None:
    observed_body: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        observed_body.update(json.loads(request.content))
        return httpx.Response(200, json=accepted_payload())

    async with adapter_for(handler) as adapter:
        result = await adapter.send(
            request_for(
                DeliveryKind.IMAGE,
                text="Imagen del pick confirmado.",
                media_url="https://cdn.buenpick.invalid/picks/pick-1.jpg",
            )
        )

    assert observed_body["type"] == "image"
    assert observed_body["image"] == {
        "link": "https://cdn.buenpick.invalid/picks/pick-1.jpg",
        "caption": "Imagen del pick confirmado.",
    }
    assert result.status is DeliveryStatus.ACCEPTED


@pytest.mark.asyncio
async def test_interactive_delivery_maps_reply_buttons() -> None:
    observed_body: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        observed_body.update(json.loads(request.content))
        return httpx.Response(200, json=accepted_payload())

    request = request_for(
        DeliveryKind.INTERACTIVE,
        text="¿Qué querés hacer?",
        interactive_options=(
            InteractiveOption(id="view-pick", title="Ver pick"),
            InteractiveOption(id="human-help", title="Pedir ayuda"),
        ),
    )
    async with adapter_for(handler) as adapter:
        await adapter.send(request)

    assert observed_body["type"] == "interactive"
    assert observed_body["interactive"] == {
        "type": "button",
        "body": {"text": "¿Qué querés hacer?"},
        "action": {
            "buttons": [
                {"type": "reply", "reply": {"id": "view-pick", "title": "Ver pick"}},
                {
                    "type": "reply",
                    "reply": {"id": "human-help", "title": "Pedir ayuda"},
                },
            ]
        },
    }


@pytest.mark.asyncio
async def test_template_delivery_maps_language_and_body_parameters() -> None:
    observed_body: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        observed_body.update(json.loads(request.content))
        return httpx.Response(200, json=accepted_payload())

    request = request_for(
        DeliveryKind.TEMPLATE,
        customer_service_window=CustomerServiceWindow.CLOSED,
        template_name="order_status_update",
        template_language="es_AR",
        template_parameters=("Orden anónima", "Lista para retirar"),
    )
    async with adapter_for(handler) as adapter:
        await adapter.send(request)

    assert observed_body["type"] == "template"
    assert observed_body["template"] == {
        "name": "order_status_update",
        "language": {"code": "es_AR"},
        "components": [
            {
                "type": "body",
                "parameters": [
                    {"type": "text", "text": "Orden anónima"},
                    {"type": "text", "text": "Lista para retirar"},
                ],
            }
        ],
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("window", "expected_code"),
    [
        (CustomerServiceWindow.CLOSED, "META_TEMPLATE_REQUIRED"),
        (CustomerServiceWindow.UNKNOWN, "META_WINDOW_UNCONFIRMED"),
    ],
)
async def test_free_form_delivery_requires_confirmed_open_window(
    window: CustomerServiceWindow, expected_code: str
) -> None:
    calls = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json=accepted_payload())

    async with adapter_for(handler) as adapter:
        result = await adapter.send(
            request_for(
                DeliveryKind.TEXT,
                text="Mensaje fuera de ventana.",
                customer_service_window=window,
            )
        )

    assert calls == 0
    assert result.status is DeliveryStatus.FAILED
    assert result.error_code == expected_code


@pytest.mark.asyncio
@pytest.mark.parametrize(("http_status", "provider_code"), [(400, 100), (503, 2)])
async def test_explicit_meta_rejection_is_failed_with_provider_code(
    http_status: int, provider_code: int
) -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            http_status,
            json={
                "error": {
                    "message": "private detail",
                    "type": "OAuthException",
                    "code": provider_code,
                }
            },
        )

    async with adapter_for(handler) as adapter:
        result = await adapter.send(request_for(DeliveryKind.TEXT, text="Mensaje"))

    assert result.status is DeliveryStatus.FAILED
    assert result.error_code == f"META_{provider_code}"
    assert result.error_message == "Meta rechazó el mensaje."
    assert result.metadata["http_status"] == http_status
    assert "private detail" not in result.error_message


@pytest.mark.asyncio
async def test_timeout_is_unknown_and_is_not_retried() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        raise httpx.ReadTimeout("uncertain provider timeout", request=request)

    async with adapter_for(handler) as adapter:
        result = await adapter.send(request_for(DeliveryKind.TEXT, text="Mensaje"))

    assert calls == 1
    assert result.status is DeliveryStatus.UNKNOWN
    assert result.error_code == "META_TIMEOUT_UNCERTAIN"
    assert result.provider_message_id is None


@pytest.mark.asyncio
async def test_invalid_success_response_is_unknown_not_success() -> None:
    async with adapter_for(lambda _: httpx.Response(200, json={"messages": []})) as adapter:
        result = await adapter.send(request_for(DeliveryKind.TEXT, text="Mensaje"))

    assert result.status is DeliveryStatus.UNKNOWN
    assert result.error_code == "META_INVALID_SUCCESS_RESPONSE"


@pytest.mark.asyncio
async def test_invalid_image_caption_fails_before_http() -> None:
    calls = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json=accepted_payload())

    async with adapter_for(handler) as adapter:
        result = await adapter.send(
            request_for(
                DeliveryKind.IMAGE,
                text="x" * 1025,
                media_url="https://cdn.buenpick.invalid/pick.jpg",
            )
        )

    assert calls == 0
    assert result.status is DeliveryStatus.FAILED
    assert result.error_code == "META_IMAGE_CAPTION_TOO_LONG"


@pytest.mark.asyncio
async def test_access_token_is_absent_from_logs(caplog: pytest.LogCaptureFixture) -> None:
    async with adapter_for(lambda _: httpx.Response(401, json={})) as adapter:
        result = await adapter.send(request_for(DeliveryKind.TEXT, text="Mensaje"))

    assert result.status is DeliveryStatus.FAILED
    assert TEST_TOKEN not in caplog.text
    assert TEST_TOKEN not in str(result)


def test_factory_requires_version_phone_and_token() -> None:
    with pytest.raises(ValueError):
        create_meta_delivery_adapter(Settings())
