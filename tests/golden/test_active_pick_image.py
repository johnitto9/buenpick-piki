from typing import Any

from piki.domain.contracts import Channel, ToolErrorCode
from piki.integrations.buenpick.client import BuenPickClientError
from piki.integrations.buenpick.models import AvailablePick
from piki.prompts.policies import PolicyName
from piki.state.active_pick import (
    ActivePickService,
    ActivePickSource,
    ConversationScope,
    RedisActivePickStore,
    StateReadStatus,
)
from piki.tools.buenpick import BuenPickTools
from piki.use_cases.pick_image import PickImagePreparer
from tests.golden.support import GoldenConversationHarness


def available_pick() -> AvailablePick:
    payload: dict[str, Any] = {
        "id": "pick-image-golden",
        "title": "Rescate sorpresa del mercado",
        "description": "Selección disponible del día.",
        "price": 150000,
        "original_price": 350000,
        "available_quantity": 1,
        "status": "AVAILABLE",
        "image_url": "https://cdn.buenpick.invalid/pick-image-golden.jpg",
        "images": ["https://cdn.buenpick.invalid/pick-image-wide.jpg"],
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
            "id": "commerce-image-golden",
            "name": "Mercado Circular",
            "description": "Comercio BuenPick",
            "address": "Dirección de fixture",
            "city": "Ciudad de fixture",
            "zone": "zona-fixture",
            "status": "active",
            "opening_hours": None,
        },
        "public_url": "https://buenpick.invalid/picks/pick-image-golden",
    }
    return AvailablePick.model_validate(payload)


class MemoryRedis:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}

    async def get(self, name: str) -> str | bytes | None:
        return self.values.get(name)

    async def set(self, name: str, value: str, *, ex: int) -> bool | None:
        self.values[name] = value
        return True

    async def delete(self, *names: str) -> int:
        return sum(self.values.pop(name, None) is not None for name in names)

    async def aclose(self) -> None:
        return None


class ImageClient:
    def __init__(self) -> None:
        self.pick = available_pick()
        self.calls: list[str] = []
        self.stale = False

    async def get_available_pick(self, pick_id: str) -> AvailablePick:
        self.calls.append(pick_id)
        if self.stale:
            raise BuenPickClientError(
                code=ToolErrorCode.NOT_FOUND,
                user_safe_message="El pick ya no está disponible.",
            )
        return self.pick


def scope() -> ConversationScope:
    return ConversationScope(
        channel=Channel.WHATSAPP,
        channel_account_id="buenpick-golden",
        conversation_id="conversation-image-golden",
    )


async def test_active_pick_photo_is_reconfirmed_and_uses_buenpick_image() -> None:
    redis = MemoryRedis()
    store = RedisActivePickStore(redis, ttl_seconds=1800)
    client = ImageClient()
    active_picks = ActivePickService(store, client)
    await active_picks.remember(scope(), client.pick, ActivePickSource.UNAMBIGUOUS_RESULT)
    preparation = await PickImagePreparer(
        active_picks,
        BuenPickTools(client),  # type: ignore[arg-type]
    ).prepare(scope(), trace_id="golden-active-image")

    assert preparation.success is True
    assert str(preparation.media_url).endswith("pick-image-wide.jpg")
    assert client.calls == ["pick-image-golden", "pick-image-golden"]

    run = await GoldenConversationHarness().run(
        policy_name=PolicyName.PICK_IMAGE,
        query="¿Me mandás la foto?",
        scripted_response="Te envío la imagen confirmada de Rescate sorpresa del mercado.",
        trace_id=preparation.trace_id,
        confirmed_data=preparation.confirmed_data,
        actions_performed=preparation.actions_performed,
        active_pick_id=preparation.active_pick_id,
    )

    assert run.outcome.used_fallback is False
    assert run.requests == ()
    assert "Rescate sorpresa del mercado" in run.outcome.text


async def test_pick_unavailable_before_photo_clears_context_and_fails_honestly() -> None:
    redis = MemoryRedis()
    store = RedisActivePickStore(redis, ttl_seconds=1800)
    client = ImageClient()
    active_picks = ActivePickService(store, client)
    await active_picks.remember(scope(), client.pick, ActivePickSource.UNAMBIGUOUS_RESULT)
    client.stale = True

    preparation = await PickImagePreparer(
        active_picks,
        BuenPickTools(client),  # type: ignore[arg-type]
    ).prepare(scope(), trace_id="golden-stale-image")

    assert preparation.success is False
    assert preparation.error_code is ToolErrorCode.NOT_FOUND
    assert preparation.user_safe_message == (
        "Ese pick ya no está disponible. Busquemos otra opción para rescatar."
    )
    assert preparation.media_url is None
    assert preparation.confirmed_data == ()
    assert client.calls == ["pick-image-golden"]
    assert (await store.get(scope())).status is StateReadStatus.MISSING
