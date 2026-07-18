import pytest
from redis.exceptions import RedisError

from piki.domain.contracts import Channel
from piki.state.active_pick import ConversationScope
from piki.state.pending_actions import (
    PendingAction,
    PendingActionKind,
    PendingActionStatus,
    RedisPendingActionStore,
)


def scope(conversation_id: str = "conversation-a") -> ConversationScope:
    return ConversationScope(
        channel=Channel.WHATSAPP,
        channel_account_id="buenpick-main",
        conversation_id=conversation_id,
    )


class FakePendingRedis:
    def __init__(self) -> None:
        self.now = 0.0
        self.values: dict[str, tuple[str, float]] = {}
        self.unavailable = False

    def advance(self, seconds: float) -> None:
        self.now += seconds

    def _check(self) -> None:
        if self.unavailable:
            raise RedisError("simulated pending-action outage")

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

    async def getdel(self, name: str) -> str | bytes | None:
        value = await self.get(name)
        if value is not None:
            self.values.pop(name, None)
        return value

    async def set(self, name: str, value: str, *, ex: int) -> bool | None:
        self._check()
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


def selection_action() -> PendingAction:
    return PendingAction(
        kind=PendingActionKind.SELECT_PICK,
        candidate_pick_ids=("pick-1", "pick-2"),
    )


@pytest.mark.asyncio
async def test_pending_action_is_isolated_and_expires() -> None:
    redis = FakePendingRedis()
    store = RedisPendingActionStore(redis, ttl_seconds=60)
    write = await store.set(scope("a"), selection_action())

    assert write.success is True
    assert (await store.get(scope("a"))).status is PendingActionStatus.FOUND
    assert (await store.get(scope("b"))).status is PendingActionStatus.MISSING

    redis.advance(60)

    assert (await store.get(scope("a"))).status is PendingActionStatus.MISSING


@pytest.mark.asyncio
async def test_consume_is_single_use() -> None:
    store = RedisPendingActionStore(FakePendingRedis(), ttl_seconds=60)
    action = PendingAction(
        kind=PendingActionKind.PROVIDE_ORDER_OWNERSHIP,
        subject_id="order-1",
    )
    await store.set(scope(), action)

    first = await store.consume(scope())
    second = await store.consume(scope())

    assert first.status is PendingActionStatus.FOUND
    assert first.action is not None
    assert first.action.action_id == action.action_id
    assert first.action.subject_id == "order-1"
    assert second.status is PendingActionStatus.MISSING


@pytest.mark.asyncio
async def test_state_outage_is_not_reported_as_missing_or_consumed() -> None:
    redis = FakePendingRedis()
    redis.unavailable = True
    store = RedisPendingActionStore(redis, ttl_seconds=60)

    write = await store.set(scope(), selection_action())
    read = await store.get(scope())
    consumed = await store.consume(scope())

    assert write.success is False
    assert write.state_available is False
    assert read.status is PendingActionStatus.UNAVAILABLE
    assert consumed.status is PendingActionStatus.UNAVAILABLE


@pytest.mark.asyncio
async def test_corrupt_pending_action_is_removed() -> None:
    redis = FakePendingRedis()
    store = RedisPendingActionStore(redis, ttl_seconds=60)
    key = store.key_for(scope())
    redis.values[key] = ("not-json", 60)

    result = await store.get(scope())

    assert result.status is PendingActionStatus.UNAVAILABLE
    assert key not in redis.values


def test_action_shapes_prevent_ambiguous_or_sensitive_state() -> None:
    invalid_inputs = (
        {
            "kind": PendingActionKind.SELECT_PICK,
            "candidate_pick_ids": ("only-one",),
        },
        {
            "kind": PendingActionKind.SELECT_PICK,
            "subject_id": "order-should-not-be-here",
            "candidate_pick_ids": ("pick-1", "pick-2"),
        },
        {
            "kind": PendingActionKind.PROVIDE_ORDER_OWNERSHIP,
            "subject_id": None,
        },
        {
            "kind": PendingActionKind.PROVIDE_ORDER_OWNERSHIP,
            "subject_id": "order-1",
            "candidate_pick_ids": ("pick-1",),
        },
    )

    for values in invalid_inputs:
        with pytest.raises(ValueError):
            PendingAction.model_validate(values)


def test_pending_action_key_hides_conversation_identity() -> None:
    key = RedisPendingActionStore.key_for(scope("phone-like-conversation"))

    assert "phone-like-conversation" not in key
    assert "buenpick-main" not in key
