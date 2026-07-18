from typing import Any

import pytest
from redis.exceptions import RedisError

from piki.domain.contracts import Channel, ToolErrorCode
from piki.integrations.buenpick.client import BuenPickClientError
from piki.integrations.buenpick.models import AvailablePick
from piki.state.active_pick import (
    ActivePickReference,
    ActivePickResolutionStatus,
    ActivePickService,
    ActivePickSource,
    ConversationScope,
    RedisActivePickStore,
    StateReadStatus,
)


def pick_payload(pick_id: str = "pick-1") -> dict[str, Any]:
    return {
        "id": pick_id,
        "title": "Pick de alimentos rescatados",
        "description": "Seleccion disponible del comercio",
        "price": 125000,
        "original_price": 280000,
        "available_quantity": 1,
        "status": "AVAILABLE",
        "image_url": "https://cdn.buenpick.invalid/pick.jpg",
        "images": ["https://cdn.buenpick.invalid/pick-wide.jpg"],
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
        "public_url": f"https://buenpick.com.ar/picks/{pick_id}",
    }


def scope(conversation_id: str = "conversation-a") -> ConversationScope:
    return ConversationScope(
        channel=Channel.WHATSAPP,
        channel_account_id="buenpick-main",
        conversation_id=conversation_id,
    )


class FakeRedis:
    def __init__(self) -> None:
        self.now = 0.0
        self.values: dict[str, tuple[str, float]] = {}
        self.unavailable = False
        self.last_ttl: int | None = None

    def advance(self, seconds: float) -> None:
        self.now += seconds

    def _check(self) -> None:
        if self.unavailable:
            raise RedisError("simulated state outage")

    async def get(self, name: str) -> str | bytes | None:
        self._check()
        stored = self.values.get(name)
        if stored is None:
            return None
        value, expires_at = stored
        if expires_at <= self.now:
            self.values.pop(name, None)
            return None
        return value

    async def set(self, name: str, value: str, *, ex: int) -> bool | None:
        self._check()
        self.last_ttl = ex
        self.values[name] = (value, self.now + ex)
        return True

    async def delete(self, *names: str) -> int:
        self._check()
        deleted = 0
        for name in names:
            deleted += int(self.values.pop(name, None) is not None)
        return deleted

    async def aclose(self) -> None:
        return None


class StubPickClient:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self.failures: dict[str, BuenPickClientError] = {}

    async def get_available_pick(self, pick_id: str) -> AvailablePick:
        self.calls.append(pick_id)
        if pick_id in self.failures:
            raise self.failures[pick_id]
        return AvailablePick.model_validate(pick_payload(pick_id))


async def remember(
    service: ActivePickService,
    target_scope: ConversationScope,
    pick_id: str,
) -> None:
    result = await service.remember(
        target_scope,
        AvailablePick.model_validate(pick_payload(pick_id)),
        ActivePickSource.UNAMBIGUOUS_RESULT,
    )
    assert result.success is True


@pytest.mark.asyncio
async def test_active_pick_is_isolated_and_key_hides_conversation_identity() -> None:
    redis = FakeRedis()
    store = RedisActivePickStore(redis, ttl_seconds=1800)
    service = ActivePickService(store, StubPickClient())
    scope_a = scope("customer-phone-a")
    scope_b = scope("customer-phone-b")

    await remember(service, scope_a, "pick-a")

    read_a = await store.get(scope_a)
    read_b = await store.get(scope_b)
    key = store.key_for(scope_a)
    assert read_a.status is StateReadStatus.FOUND
    assert read_a.reference is not None
    assert read_a.reference.pick_id == "pick-a"
    assert read_b.status is StateReadStatus.MISSING
    assert "customer-phone-a" not in key
    assert "buenpick-main" not in key


@pytest.mark.asyncio
async def test_active_pick_ttl_expires_without_stale_carryover() -> None:
    redis = FakeRedis()
    store = RedisActivePickStore(redis, ttl_seconds=60)
    service = ActivePickService(store, StubPickClient())

    await remember(service, scope(), "pick-1")
    assert redis.last_ttl == 60
    assert (await store.get(scope())).status is StateReadStatus.FOUND

    redis.advance(60)

    assert (await store.get(scope())).status is StateReadStatus.MISSING


@pytest.mark.asyncio
async def test_inherited_active_pick_is_reconfirmed_with_buenpick() -> None:
    redis = FakeRedis()
    client = StubPickClient()
    service = ActivePickService(RedisActivePickStore(redis, ttl_seconds=60), client)
    await remember(service, scope(), "pick-1")

    resolution = await service.resolve(scope())

    assert resolution.status is ActivePickResolutionStatus.CONFIRMED
    assert resolution.pick is not None
    assert resolution.pick.id == "pick-1"
    assert resolution.source is ActivePickSource.UNAMBIGUOUS_RESULT
    assert resolution.context_persisted is True
    assert client.calls == ["pick-1"]


@pytest.mark.asyncio
async def test_explicit_pick_precedes_and_replaces_inherited_context() -> None:
    redis = FakeRedis()
    store = RedisActivePickStore(redis, ttl_seconds=60)
    client = StubPickClient()
    service = ActivePickService(store, client)
    await remember(service, scope(), "pick-old")

    resolution = await service.resolve(scope(), explicit_pick_id="pick-new")
    active = await store.get(scope())

    assert resolution.status is ActivePickResolutionStatus.CONFIRMED
    assert resolution.pick is not None
    assert resolution.pick.id == "pick-new"
    assert resolution.source is ActivePickSource.EXPLICIT_REFERENCE
    assert active.reference is not None
    assert active.reference.pick_id == "pick-new"
    assert client.calls == ["pick-new"]


@pytest.mark.asyncio
async def test_stale_inherited_pick_is_cleared_after_buenpick_404() -> None:
    redis = FakeRedis()
    store = RedisActivePickStore(redis, ttl_seconds=60)
    client = StubPickClient()
    client.failures["pick-stale"] = BuenPickClientError(
        code=ToolErrorCode.NOT_FOUND,
        user_safe_message="No pude confirmar que el pick siga disponible.",
    )
    service = ActivePickService(store, client)
    await remember(service, scope(), "pick-stale")

    resolution = await service.resolve(scope())

    assert resolution.status is ActivePickResolutionStatus.STALE
    assert resolution.pick is None
    assert (await store.get(scope())).status is StateReadStatus.MISSING


@pytest.mark.asyncio
async def test_redis_outage_has_honest_fallback_without_global_memory() -> None:
    redis = FakeRedis()
    redis.unavailable = True
    client = StubPickClient()
    service = ActivePickService(RedisActivePickStore(redis, ttl_seconds=60), client)

    inherited = await service.resolve(scope())
    explicit = await service.resolve(scope(), explicit_pick_id="pick-explicit")

    assert inherited.status is ActivePickResolutionStatus.STATE_UNAVAILABLE
    assert inherited.pick is None
    assert explicit.status is ActivePickResolutionStatus.CONFIRMED
    assert explicit.pick is not None
    assert explicit.context_persisted is False
    assert client.calls == ["pick-explicit"]


@pytest.mark.asyncio
async def test_corrupt_state_is_removed_and_reported_unavailable() -> None:
    redis = FakeRedis()
    store = RedisActivePickStore(redis, ttl_seconds=60)
    redis.values[store.key_for(scope())] = ("not-json", 60)

    result = await store.get(scope())

    assert result.status is StateReadStatus.UNAVAILABLE
    assert store.key_for(scope()) not in redis.values


def test_active_pick_reference_rejects_naive_timestamp() -> None:
    with pytest.raises(ValueError):
        ActivePickReference(
            pick_id="pick-1",
            commerce_id="commerce-1",
            selected_at="2026-07-16T12:00:00",
            source=ActivePickSource.EXPLICIT_REFERENCE,
        )
