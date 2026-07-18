import hashlib
import secrets
from collections.abc import Awaitable
from enum import StrEnum
from typing import Protocol, cast

from pydantic import Field, model_validator
from redis.asyncio import Redis
from redis.exceptions import RedisError

from piki.core.config import Settings
from piki.domain.contracts import ContractModel
from piki.state.active_pick import ConversationScope, conversation_scope_digest

RELEASE_LOCK_SCRIPT = """
if redis.call('get', KEYS[1]) == ARGV[1] then
  return redis.call('del', KEYS[1])
end
return 0
""".strip()


class CoordinationRedis(Protocol):
    def set(
        self, name: str, value: str, *, ex: int, nx: bool = False
    ) -> Awaitable[bool | None]: ...

    def eval(
        self, script: str, numkeys: int, *keys_and_args: str
    ) -> Awaitable[int]: ...

    def aclose(self) -> Awaitable[None]: ...


class LockStatus(StrEnum):
    ACQUIRED = "acquired"
    BUSY = "busy"
    UNAVAILABLE = "unavailable"


class LockLease(ContractModel):
    status: LockStatus
    owner_token: str | None = Field(default=None, min_length=32, max_length=128)

    @model_validator(mode="after")
    def validate_shape(self) -> "LockLease":
        if (self.status is LockStatus.ACQUIRED) != (self.owner_token is not None):
            raise ValueError("only acquired locks contain an owner token")
        return self


class LockReleaseStatus(StrEnum):
    RELEASED = "released"
    NOT_OWNER = "not_owner"
    UNAVAILABLE = "unavailable"


class DedupStatus(StrEnum):
    CLAIMED = "claimed"
    DUPLICATE = "duplicate"
    UNAVAILABLE = "unavailable"


class RedisConversationLock:
    key_prefix = "piki:v1:conversation"

    def __init__(self, redis: CoordinationRedis, *, ttl_seconds: int) -> None:
        if ttl_seconds < 1:
            raise ValueError("lock TTL must be positive")
        self._redis = redis
        self._ttl_seconds = ttl_seconds

    @classmethod
    def key_for(cls, scope: ConversationScope) -> str:
        return f"{cls.key_prefix}:{conversation_scope_digest(scope)}:lock"

    async def acquire(self, scope: ConversationScope) -> LockLease:
        owner_token = secrets.token_urlsafe(32)
        try:
            acquired = await self._redis.set(
                self.key_for(scope), owner_token, ex=self._ttl_seconds, nx=True
            )
        except RedisError:
            return LockLease(status=LockStatus.UNAVAILABLE)
        if not acquired:
            return LockLease(status=LockStatus.BUSY)
        return LockLease(status=LockStatus.ACQUIRED, owner_token=owner_token)

    async def release(
        self, scope: ConversationScope, owner_token: str
    ) -> LockReleaseStatus:
        try:
            released = await self._redis.eval(
                RELEASE_LOCK_SCRIPT,
                1,
                self.key_for(scope),
                owner_token,
            )
        except RedisError:
            return LockReleaseStatus.UNAVAILABLE
        if released == 1:
            return LockReleaseStatus.RELEASED
        return LockReleaseStatus.NOT_OWNER


class RedisMessageDeduplicator:
    key_prefix = "piki:v1:inbound-message"

    def __init__(self, redis: CoordinationRedis, *, ttl_seconds: int) -> None:
        if ttl_seconds < 1:
            raise ValueError("dedup TTL must be positive")
        self._redis = redis
        self._ttl_seconds = ttl_seconds

    @classmethod
    def key_for(cls, channel_account_id: str, message_id: str) -> str:
        identity = "\x1f".join((channel_account_id, message_id))
        digest = hashlib.sha256(identity.encode()).hexdigest()
        return f"{cls.key_prefix}:{digest}"

    async def claim(self, channel_account_id: str, message_id: str) -> DedupStatus:
        if not channel_account_id.strip() or not message_id.strip():
            raise ValueError("dedup identity parts cannot be blank")
        try:
            claimed = await self._redis.set(
                self.key_for(channel_account_id, message_id),
                "1",
                ex=self._ttl_seconds,
                nx=True,
            )
        except RedisError:
            return DedupStatus.UNAVAILABLE
        return DedupStatus.CLAIMED if claimed else DedupStatus.DUPLICATE


class RedisCoordination:
    def __init__(self, redis: CoordinationRedis, settings: Settings) -> None:
        self.locks = RedisConversationLock(
            redis, ttl_seconds=settings.conversation_lock_ttl_seconds
        )
        self.messages = RedisMessageDeduplicator(
            redis, ttl_seconds=settings.message_dedup_ttl_seconds
        )
        self._redis = redis

    async def close(self) -> None:
        await self._redis.aclose()


def create_redis_coordination(settings: Settings) -> RedisCoordination:
    redis = cast(
        CoordinationRedis,
        Redis.from_url(settings.redis_url, decode_responses=True),
    )
    return RedisCoordination(redis, settings)
