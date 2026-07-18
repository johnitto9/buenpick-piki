from typing import Any

import pytest

from piki.domain.contracts import ToolErrorCode
from piki.integrations.buenpick.client import BuenPickClientError
from piki.integrations.buenpick.models import (
    AvailablePick,
    Commerce,
    CustomerOrder,
    PickSearchResponse,
)
from piki.observability.events import (
    EventOutcome,
    LifecycleEvent,
    LifecycleObserver,
    RecordingEventSink,
)
from piki.tools.buenpick import BuenPickTools


def pick_payload(*, with_image: bool = True) -> dict[str, Any]:
    image_url = "https://cdn.buenpick.invalid/pick.jpg" if with_image else None
    images = ["https://cdn.buenpick.invalid/pick-wide.jpg"] if with_image else []
    return {
        "id": "pick-1",
        "title": "Pick de alimentos rescatados",
        "description": "Seleccion del comercio",
        "price": 100000,
        "original_price": 220000,
        "available_quantity": 1,
        "status": "AVAILABLE",
        "image_url": image_url,
        "images": images,
        "category": "almacen",
        "pickup": {
            "starts_at": "2026-07-16T18:00:00Z",
            "ends_at": "2026-07-16T20:00:00Z",
        },
        "conditions": {
            "quantity_available": 1,
            "approx_weight_grams": None,
            "fulfillment": {
                "pickup": True,
                "delivery_enabled": False,
                "delivery_eta_min_minutes": None,
                "delivery_eta_max_minutes": None,
            },
        },
        "commerce": {
            "id": "commerce-1",
            "name": "Mercado Circular",
            "description": "Comercio BuenPick",
            "address": "Sarmiento 456",
            "city": "Bahia Blanca",
            "zone": "macrocentro",
            "status": "active",
            "opening_hours": None,
        },
        "public_url": "https://buenpick.com.ar/picks/pick-1",
    }


class StubBuenPickClient:
    def __init__(self, *, pick: AvailablePick | None = None) -> None:
        self.pick = pick or AvailablePick.model_validate(pick_payload())
        self.error: BuenPickClientError | None = None

    def fail_with(self, error: BuenPickClientError) -> None:
        self.error = error

    def _raise_if_failed(self) -> None:
        if self.error is not None:
            raise self.error

    async def search_available_picks(
        self, query: str | None = None, commerce_id: str | None = None
    ) -> PickSearchResponse:
        self._raise_if_failed()
        return PickSearchResponse(items=(), total=0)

    async def get_available_pick(self, pick_id: str) -> AvailablePick:
        self._raise_if_failed()
        return self.pick

    async def get_commerce(self, commerce_id: str) -> Commerce:
        self._raise_if_failed()
        raise AssertionError("not needed by this unit test")

    async def get_customer_order(
        self,
        order_id: str,
        *,
        customer_phone: str | None = None,
        customer_reference: str | None = None,
    ) -> CustomerOrder:
        self._raise_if_failed()
        raise AssertionError("not needed by this unit test")


@pytest.mark.asyncio
async def test_empty_search_remains_a_successful_tool_result() -> None:
    tools = BuenPickTools(StubBuenPickClient())

    result = await tools.search_available_picks(
        query="verduras", commerce_id=None, trace_id="trace-search"
    )

    assert result.success is True
    assert result.data is not None
    assert result.data.items == ()
    assert result.error_code is None


@pytest.mark.asyncio
async def test_tool_preserves_typed_safe_upstream_failure() -> None:
    client = StubBuenPickClient()
    client.fail_with(
        BuenPickClientError(
            code=ToolErrorCode.NOT_FOUND,
            user_safe_message="No pude confirmar que el pick siga disponible.",
        )
    )
    tools = BuenPickTools(client)

    result = await tools.get_available_pick(pick_id="pick-1", trace_id="trace-pick")

    assert result.success is False
    assert result.data is None
    assert result.error_code is ToolErrorCode.NOT_FOUND
    assert result.trace_id == "trace-pick"


@pytest.mark.asyncio
async def test_image_tool_prefers_confirmed_images_array() -> None:
    tools = BuenPickTools(StubBuenPickClient())

    result = await tools.get_pick_image(pick_id="pick-1", trace_id="trace-image")

    assert result.success is True
    assert result.data is not None
    assert str(result.data.image_url).endswith("pick-wide.jpg")


@pytest.mark.asyncio
async def test_image_tool_fails_when_api_has_no_image_evidence() -> None:
    pick = AvailablePick.model_validate(pick_payload(with_image=False))
    tools = BuenPickTools(StubBuenPickClient(pick=pick))

    result = await tools.get_pick_image(pick_id="pick-1", trace_id="trace-no-image")

    assert result.success is False
    assert result.error_code is ToolErrorCode.NOT_FOUND
    assert result.data is None


async def test_tool_events_share_trace_latency_and_typed_failure() -> None:
    sink = RecordingEventSink()
    observer = LifecycleObserver(sink)
    client = StubBuenPickClient()
    tools = BuenPickTools(client, observer=observer)

    success = await tools.search_available_picks(
        query="fixture", commerce_id=None, trace_id="trace-tool-observation"
    )
    client.fail_with(
        BuenPickClientError(
            code=ToolErrorCode.TIMEOUT,
            user_safe_message="BuenPick tardó demasiado en responder.",
        )
    )
    failure = await tools.get_available_pick(
        pick_id="pick-fixture", trace_id="trace-tool-observation"
    )

    assert success.success is True
    assert failure.error_code is ToolErrorCode.TIMEOUT
    assert [record.event for record in sink.records] == [
        LifecycleEvent.TOOL_STARTED,
        LifecycleEvent.TOOL_FINISHED,
        LifecycleEvent.TOOL_STARTED,
        LifecycleEvent.TOOL_FINISHED,
    ]
    assert sink.records[1].outcome is EventOutcome.SUCCEEDED
    assert sink.records[3].outcome is EventOutcome.FAILED
    assert sink.records[3].error_code == "timeout"
    assert all(record.trace_id == "trace-tool-observation" for record in sink.records)
    assert all(record.duration_ms >= 0 for record in sink.records)
