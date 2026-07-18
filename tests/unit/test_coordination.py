import pytest
from redis.exceptions import RedisError

from piki.domain.contracts import Channel
from piki.state.active_pick import ConversationScope
from piki.state.coordination import (
    RELEASE_LOCK_SCRIPT,
    DedupStatus,
    LockReleaseStatus,
    LockStatus,
    RedisConversationLock,
    RedisMessageDeduplicator,
)


def scope(conversation_id: str = "conversation-a") -> ConversationScope:
    return ConversationScope(
        channel=Channel.WHATSAPP,
        channel_account_id="buenpick-main",
        conversation_id=conversation_id,
    )


class FakeCoordinationRedis:
    def __init__(self) -> None:
        self.now = 0.0
        self.values: dict[str, tuple[str, float]] = {}
        self.unavailable = False

    def advance(self, seconds: float) -> None:
        self.now += seconds

    def _check(self) -> None:
        if self.unavailable:
            raise RedisError("simulated coordination outage")

    def _current(self, name: str) -> str | None:
        stored = self.values.get(name)
        if stored is None:
            return None
        value, expires_at = stored
        if expires_at <= self.now:
            self.values.pop(name, None)
            return None
        return value

    async def set(
        self, name: str, value: str, *, ex: int, nx: bool = False
    ) -> bool | None:
        self._check()
        if nx and self._current(name) is not None:
            return None
        self.values[name] = (value, self.now + ex)
        return True

    async def eval(self, script: str, numkeys: int, *keys_and_args: str) -> int:
        self._check()
        assert script == RELEASE_LOCK_SCRIPT
        assert numkeys == 1
        key, expected_value = keys_and_args
        if self._current(key) != expected_value:
            return 0
        self.values.pop(key, None)
        return 1

    async def aclose(self) -> None:
        return None


@pytest.mark.asyncio
async def test_lock_is_exclusive_and_isolated_by_conversation() -> None:
    redis = FakeCoordinationRedis()
    locks = RedisConversationLock(redis, ttl_seconds=30)

    first_a = await locks.acquire(scope("a"))
    second_a = await locks.acquire(scope("a"))
    first_b = await locks.acquire(scope("b"))

    assert first_a.status is LockStatus.ACQUIRED
    assert first_a.owner_token is not None
    assert second_a.status is LockStatus.BUSY
    assert second_a.owner_token is None
    assert first_b.status is LockStatus.ACQUIRED


@pytest.mark.asyncio
async def test_only_owner_can_release_lock() -> None:
    redis = FakeCoordinationRedis()
    locks = RedisConversationLock(redis, ttl_seconds=30)
    lease = await locks.acquire(scope())
    assert lease.owner_token is not None

    wrong_release = await locks.release(scope(), "x" * 43)
    still_busy = await locks.acquire(scope())
    owner_release = await locks.release(scope(), lease.owner_token)
    reacquired = await locks.acquire(scope())

    assert wrong_release is LockReleaseStatus.NOT_OWNER
    assert still_busy.status is LockStatus.BUSY
    assert owner_release is LockReleaseStatus.RELEASED
    assert reacquired.status is LockStatus.ACQUIRED


@pytest.mark.asyncio
async def test_expired_lock_does_not_block_new_worker() -> None:
    redis = FakeCoordinationRedis()
    locks = RedisConversationLock(redis, ttl_seconds=5)
    assert (await locks.acquire(scope())).status is LockStatus.ACQUIRED

    redis.advance(5)

    assert (await locks.acquire(scope())).status is LockStatus.ACQUIRED


@pytest.mark.asyncio
async def test_message_claim_is_atomic_scoped_and_expires() -> None:
    redis = FakeCoordinationRedis()
    dedup = RedisMessageDeduplicator(redis, ttl_seconds=60)

    first = await dedup.claim("account-a", "wamid.123")
    duplicate = await dedup.claim("account-a", "wamid.123")
    other_account = await dedup.claim("account-b", "wamid.123")
    redis.advance(60)
    after_expiry = await dedup.claim("account-a", "wamid.123")

    assert first is DedupStatus.CLAIMED
    assert duplicate is DedupStatus.DUPLICATE
    assert other_account is DedupStatus.CLAIMED
    assert after_expiry is DedupStatus.CLAIMED


@pytest.mark.asyncio
async def test_coordination_outage_never_claims_or_acquires() -> None:
    redis = FakeCoordinationRedis()
    redis.unavailable = True
    locks = RedisConversationLock(redis, ttl_seconds=30)
    dedup = RedisMessageDeduplicator(redis, ttl_seconds=60)

    lease = await locks.acquire(scope())
    release = await locks.release(scope(), "x" * 43)
    claim = await dedup.claim("account-a", "wamid.123")

    assert lease.status is LockStatus.UNAVAILABLE
    assert release is LockReleaseStatus.UNAVAILABLE
    assert claim is DedupStatus.UNAVAILABLE


def test_coordination_keys_do_not_expose_external_identifiers() -> None:
    lock_key = RedisConversationLock.key_for(scope("phone-like-conversation"))
    dedup_key = RedisMessageDeduplicator.key_for("account-a", "wamid.visible")

    assert "phone-like-conversation" not in lock_key
    assert "account-a" not in dedup_key
    assert "wamid.visible" not in dedup_key


@pytest.mark.asyncio
async def test_blank_dedup_identity_is_rejected_before_redis() -> None:
    dedup = RedisMessageDeduplicator(FakeCoordinationRedis(), ttl_seconds=60)

    with pytest.raises(ValueError):
        await dedup.claim("account-a", " ")
