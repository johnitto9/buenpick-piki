from collections.abc import Awaitable
from datetime import UTC, datetime
from enum import StrEnum
from typing import Protocol, cast
from uuid import uuid4

from pydantic import Field, model_validator
from redis.asyncio import Redis
from redis.exceptions import RedisError

from piki.core.config import Settings
from piki.domain.contracts import ContractModel
from piki.state.active_pick import ConversationScope, conversation_scope_digest


class PendingActionKind(StrEnum):
    SELECT_PICK = "select_pick"
    PROVIDE_ORDER_OWNERSHIP = "provide_order_ownership"


class PendingAction(ContractModel):
    schema_version: str = "1.0"
    action_id: str = Field(default_factory=lambda: str(uuid4()), min_length=36, max_length=36)
    kind: PendingActionKind
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    subject_id: str | None = Field(default=None, min_length=1, max_length=255)
    candidate_pick_ids: tuple[str, ...] = Field(default=(), max_length=20)

    @model_validator(mode="after")
    def validate_shape(self) -> "PendingAction":
        if self.created_at.tzinfo is None:
            raise ValueError("created_at must include a timezone")
        if self.kind is PendingActionKind.SELECT_PICK:
            if len(self.candidate_pick_ids) < 2 or self.subject_id is not None:
                raise ValueError("pick selection requires at least two candidates and no subject")
        elif self.kind is PendingActionKind.PROVIDE_ORDER_OWNERSHIP:
            if self.subject_id is None or self.candidate_pick_ids:
                raise ValueError("order ownership requires one subject and no candidates")
        if any(not pick_id.strip() for pick_id in self.candidate_pick_ids):
            raise ValueError("candidate pick IDs cannot be blank")
        if len(set(self.candidate_pick_ids)) != len(self.candidate_pick_ids):
            raise ValueError("candidate pick IDs must be unique")
        return self


class PendingActionStatus(StrEnum):
    FOUND = "found"
    MISSING = "missing"
    UNAVAILABLE = "unavailable"


class PendingActionRead(ContractModel):
    status: PendingActionStatus
    action: PendingAction | None = None

    @model_validator(mode="after")
    def validate_shape(self) -> "PendingActionRead":
        if (self.status is PendingActionStatus.FOUND) != (self.action is not None):
            raise ValueError("only found pending-action reads contain an action")
        return self


class PendingActionWrite(ContractModel):
    success: bool
    state_available: bool

    @model_validator(mode="after")
    def validate_shape(self) -> "PendingActionWrite":
        if self.success and not self.state_available:
            raise ValueError("successful pending-action writes require available state")
        return self


class PendingActionRedis(Protocol):
    def get(self, name: str) -> Awaitable[str | bytes | None]: ...

    def getdel(self, name: str) -> Awaitable[str | bytes | None]: ...

    def set(self, name: str, value: str, *, ex: int) -> Awaitable[bool | None]: ...

    def delete(self, *names: str) -> Awaitable[int]: ...

    def aclose(self) -> Awaitable[None]: ...


class RedisPendingActionStore:
    key_prefix = "piki:v1:conversation"

    def __init__(self, redis: PendingActionRedis, *, ttl_seconds: int) -> None:
        if ttl_seconds < 1:
            raise ValueError("pending-action TTL must be positive")
        self._redis = redis
        self._ttl_seconds = ttl_seconds

    @classmethod
    def key_for(cls, scope: ConversationScope) -> str:
        return f"{cls.key_prefix}:{conversation_scope_digest(scope)}:pending-action"

    async def close(self) -> None:
        await self._redis.aclose()

    async def set(
        self, scope: ConversationScope, action: PendingAction
    ) -> PendingActionWrite:
        try:
            stored = await self._redis.set(
                self.key_for(scope), action.model_dump_json(), ex=self._ttl_seconds
            )
        except RedisError:
            return PendingActionWrite(success=False, state_available=False)
        return PendingActionWrite(success=bool(stored), state_available=True)

    async def get(self, scope: ConversationScope) -> PendingActionRead:
        try:
            payload = await self._redis.get(self.key_for(scope))
        except RedisError:
            return PendingActionRead(status=PendingActionStatus.UNAVAILABLE)
        return await self._parse(scope, payload, consumed=False)

    async def consume(self, scope: ConversationScope) -> PendingActionRead:
        try:
            payload = await self._redis.getdel(self.key_for(scope))
        except RedisError:
            return PendingActionRead(status=PendingActionStatus.UNAVAILABLE)
        return await self._parse(scope, payload, consumed=True)

    async def clear(self, scope: ConversationScope) -> PendingActionWrite:
        try:
            await self._redis.delete(self.key_for(scope))
        except RedisError:
            return PendingActionWrite(success=False, state_available=False)
        return PendingActionWrite(success=True, state_available=True)

    async def _parse(
        self,
        scope: ConversationScope,
        payload: str | bytes | None,
        *,
        consumed: bool,
    ) -> PendingActionRead:
        if payload is None:
            return PendingActionRead(status=PendingActionStatus.MISSING)
        try:
            action = PendingAction.model_validate_json(payload)
        except ValueError:
            if not consumed:
                await self.clear(scope)
            return PendingActionRead(status=PendingActionStatus.UNAVAILABLE)
        return PendingActionRead(status=PendingActionStatus.FOUND, action=action)


def create_pending_action_store(settings: Settings) -> RedisPendingActionStore:
    redis = cast(
        PendingActionRedis,
        Redis.from_url(settings.redis_url, decode_responses=True),
    )
    return RedisPendingActionStore(redis, ttl_seconds=settings.pending_action_ttl_seconds)
