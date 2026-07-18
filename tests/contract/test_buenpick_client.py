from collections.abc import Callable
from typing import Any

import httpx
import pytest
from pydantic import SecretStr

from piki.core.config import Settings
from piki.domain.contracts import ToolErrorCode
from piki.integrations.buenpick.client import (
    BuenPickClient,
    BuenPickClientError,
    BuenPickConfigurationError,
    CheckoutDisabledError,
    create_buenpick_client,
)
from piki.integrations.buenpick.models import format_ars_cents

Handler = Callable[[httpx.Request], httpx.Response]
TEST_TOKEN = "contract-test-token"  # noqa: S105 - inert mock credential


def pick_summary() -> dict[str, Any]:
    return {
        "id": "pick-bakery-1",
        "title": "Bolsa sorpresa de panaderia",
        "description": "Excedentes frescos del dia",
        "price": 250000,
        "original_price": 600000,
        "available_quantity": 2,
        "status": "AVAILABLE",
        "image_url": "https://cdn.buenpick.invalid/picks/bakery-1.jpg",
        "commerce": {"id": "commerce-1", "name": "Panaderia Centro"},
    }


def available_pick() -> dict[str, Any]:
    return {
        **pick_summary(),
        "images": ["https://cdn.buenpick.invalid/picks/bakery-1-wide.jpg"],
        "category": "panaderia",
        "pickup": {
            "starts_at": "2026-07-16T18:00:00.000Z",
            "ends_at": "2026-07-16T21:00:00.000Z",
        },
        "conditions": {
            "quantity_available": 2,
            "approx_weight_grams": 800,
            "fulfillment": {
                "pickup": True,
                "delivery_enabled": False,
                "delivery_eta_min_minutes": None,
                "delivery_eta_max_minutes": None,
            },
        },
        "commerce": {
            "id": "commerce-1",
            "name": "Panaderia Centro",
            "description": "Panes y facturas rescatados",
            "address": "Alsina 123",
            "city": "Bahia Blanca",
            "zone": "centro",
            "status": "active",
            "opening_hours": None,
        },
        "public_url": "https://buenpick.com.ar/picks/pick-bakery-1",
    }


def customer_order() -> dict[str, Any]:
    return {
        "id": "order-1",
        "status": "paid",
        "commerce": {
            "id": "commerce-1",
            "name": "Panaderia Centro",
            "address": "Alsina 123",
            "opening_hours": None,
        },
        "picks": [
            {
                "pick_id": "pick-bakery-1",
                "title": "Bolsa sorpresa de panaderia",
                "quantity": 1,
                "unit_price": 250000,
                "line_total": 250000,
                "image_url": "https://cdn.buenpick.invalid/picks/bakery-1.jpg",
            }
        ],
        "total": 250000,
        "fulfillment": {
            "type": "pickup",
            "delivery_address": None,
            "delivery_notes": None,
            "pickup_code": "ABC123",
        },
        "pickup": {"instructions": None, "store_address": "Alsina 123"},
        "dates": {
            "created_at": "2026-07-16T10:00:00.000Z",
            "expires_at": None,
            "confirmed_at": "2026-07-16T10:02:00.000Z",
            "paid_at": "2026-07-16T10:02:00.000Z",
            "preparing_at": None,
            "ready_at": None,
            "out_for_delivery_at": None,
            "delivered_at": None,
            "picked_up_at": None,
        },
    }


def commerce() -> dict[str, Any]:
    return {
        "id": "commerce-1",
        "name": "Panaderia Centro",
        "slug": "panaderia-centro",
        "description": "Panes y facturas rescatados",
        "address": "Alsina 123",
        "city": "Bahia Blanca",
        "zone": "centro",
        "phone": "2914555555",
        "status": "active",
        "opening_hours": None,
        "pickup_instructions": None,
        "delivery": {
            "enabled": False,
            "fee_cents": None,
            "eta_min_minutes": None,
            "eta_max_minutes": None,
        },
        "accepts_cash_on_pickup": True,
        "logo_url": "https://cdn.buenpick.invalid/commerces/commerce-1.jpg",
        "cover_url": None,
    }


async def no_sleep(_: float) -> None:
    return None


def client_for(handler: Handler, *, max_attempts: int = 3) -> BuenPickClient:
    return BuenPickClient(
        base_url="https://mock.buenpick.invalid/internal/v1",
        token=SecretStr(TEST_TOKEN),
        max_attempts=max_attempts,
        transport=httpx.MockTransport(handler),
        sleep=no_sleep,
    )


@pytest.mark.asyncio
async def test_empty_search_is_success_and_sends_filters_and_bearer_token() -> None:
    observed: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        observed.append(request)
        return httpx.Response(200, json={"items": [], "total": 0})

    async with client_for(handler) as client:
        result = await client.search_available_picks(" pan ", " commerce-1 ")

    assert result.items == ()
    assert result.total == 0
    assert observed[0].url.path == "/internal/v1/picks/search"
    assert dict(observed[0].url.params) == {"q": "pan", "commerce_id": "commerce-1"}
    assert observed[0].headers["Authorization"] == f"Bearer {TEST_TOKEN}"


@pytest.mark.asyncio
async def test_pick_detail_validates_contract_and_url_encodes_identifier() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.raw_path.endswith(b"/picks/pick%2Funsafe")
        return httpx.Response(200, json=available_pick())

    async with client_for(handler) as client:
        result = await client.get_available_pick("pick/unsafe")

    assert result.id == "pick-bakery-1"
    assert result.conditions.fulfillment.delivery_enabled is False
    assert str(result.public_url).endswith("/picks/pick-bakery-1")


@pytest.mark.asyncio
async def test_unavailable_pick_maps_404_without_claiming_why() -> None:
    async with client_for(lambda _: httpx.Response(404, json={"error": {}})) as client:
        with pytest.raises(BuenPickClientError) as raised:
            await client.get_available_pick("missing")

    assert raised.value.code is ToolErrorCode.NOT_FOUND
    assert raised.value.status_code == 404
    assert "recurso" in raised.value.user_safe_message


@pytest.mark.asyncio
async def test_commerce_contract_preserves_nullable_operational_fields() -> None:
    async with client_for(lambda _: httpx.Response(200, json=commerce())) as client:
        result = await client.get_commerce("commerce-1")

    assert result.name == "Panaderia Centro"
    assert result.opening_hours is None
    assert result.delivery.enabled is False
    assert result.delivery.fee_cents is None


@pytest.mark.asyncio
async def test_order_requires_exactly_one_ownership_proof_before_network() -> None:
    calls = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json=customer_order())

    async with client_for(handler) as client:
        for phone, reference in ((None, None), ("2914555555", "user-1")):
            with pytest.raises(BuenPickClientError) as raised:
                await client.get_customer_order(
                    "order-1", customer_phone=phone, customer_reference=reference
                )
            assert raised.value.code is ToolErrorCode.BAD_REQUEST

    assert calls == 0


@pytest.mark.asyncio
async def test_order_ownership_failure_is_non_enumerating() -> None:
    async with client_for(lambda _: httpx.Response(401, json={"error": {}})) as client:
        with pytest.raises(BuenPickClientError) as raised:
            await client.get_customer_order("order-1", customer_phone="2914555555")

    assert raised.value.code is ToolErrorCode.UNAUTHORIZED
    assert "pertenencia" in raised.value.user_safe_message
    assert "order-1" not in str(raised.value)


@pytest.mark.asyncio
async def test_owned_order_passes_normalized_phone_and_validates_payload() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert dict(request.url.params) == {"customer_phone": "2914555555"}
        return httpx.Response(200, json=customer_order())

    async with client_for(handler) as client:
        result = await client.get_customer_order(
            "order-1", customer_phone=" 2914555555 "
        )

    assert result.id == "order-1"
    assert result.fulfillment.pickup_code == "ABC123"


@pytest.mark.asyncio
async def test_retryable_responses_use_bounded_retries() -> None:
    statuses = iter((503, 429, 200))
    sleeps: list[float] = []

    async def record_sleep(delay: float) -> None:
        sleeps.append(delay)

    def handler(_: httpx.Request) -> httpx.Response:
        status = next(statuses)
        payload = {"items": [pick_summary()], "total": 1} if status == 200 else {}
        return httpx.Response(status, json=payload)

    client = BuenPickClient(
        base_url="https://mock.buenpick.invalid/internal/v1",
        token=SecretStr(TEST_TOKEN),
        transport=httpx.MockTransport(handler),
        sleep=record_sleep,
    )
    async with client:
        result = await client.search_available_picks()

    assert result.total == 1
    assert sleeps == [0.1, 0.2]


@pytest.mark.asyncio
async def test_timeout_exhaustion_returns_safe_error() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        raise httpx.ReadTimeout("simulated timeout", request=request)

    async with client_for(handler, max_attempts=2) as client:
        with pytest.raises(BuenPickClientError) as raised:
            await client.search_available_picks()

    assert calls == 2
    assert raised.value.code is ToolErrorCode.TIMEOUT
    assert "simulated" not in raised.value.user_safe_message


@pytest.mark.asyncio
async def test_invalid_upstream_schema_fails_closed() -> None:
    payload = {"items": [{**pick_summary(), "available_quantity": -1}], "total": 1}
    async with client_for(lambda _: httpx.Response(200, json=payload)) as client:
        with pytest.raises(BuenPickClientError) as raised:
            await client.search_available_picks()

    assert raised.value.code is ToolErrorCode.INTERNAL_ERROR


def test_production_access_requires_explicit_runtime_opt_in() -> None:
    with pytest.raises(BuenPickConfigurationError):
        BuenPickClient(
            base_url="https://api.buenpick.com.ar/internal/v1",
            token=SecretStr("never-sent"),
        )


def test_client_factory_requires_configured_token() -> None:
    with pytest.raises(BuenPickConfigurationError):
        create_buenpick_client(Settings(buenpick_internal_api_token=None))


@pytest.mark.asyncio
async def test_token_is_absent_from_logs_and_safe_error(caplog: pytest.LogCaptureFixture) -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"error": {"message": "upstream detail"}})

    async with client_for(handler, max_attempts=1) as client:
        with pytest.raises(BuenPickClientError) as raised:
            await client.search_available_picks()

    assert TEST_TOKEN not in caplog.text
    assert TEST_TOKEN not in str(raised.value)
    assert "upstream detail" not in raised.value.user_safe_message


@pytest.mark.asyncio
async def test_checkout_is_locally_disabled_without_http_request() -> None:
    calls = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(500)

    async with client_for(handler) as client:
        with pytest.raises(CheckoutDisabledError):
            await client.create_checkout_session()

    assert calls == 0


def test_ars_cents_formatting_is_explicit() -> None:
    assert format_ars_cents(250000) == "$2.500,00"
    assert format_ars_cents(0) == "$0,00"
    with pytest.raises(ValueError):
        format_ars_cents(-1)
