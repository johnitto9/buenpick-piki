import hashlib
from collections.abc import Awaitable
from datetime import UTC, datetime
from enum import StrEnum
from typing import Protocol, cast

from pydantic import Field, model_validator
from redis.asyncio import Redis
from redis.exceptions import RedisError

from piki.core.config import Settings
from piki.domain.contracts import Channel, ContractModel, ToolErrorCode
from piki.integrations.buenpick.client import BuenPickClientError
from piki.integrations.buenpick.models import AvailablePick


class ConversationScope(ContractModel):
    channel: Channel
    channel_account_id: str = Field(min_length=1, max_length=255)
    conversation_id: str = Field(min_length=1, max_length=255)


class ActivePickSource(StrEnum):
    EXPLICIT_REFERENCE = "explicit_reference"
    UNAMBIGUOUS_RESULT = "unambiguous_result"


class ActivePickReference(ContractModel):
    schema_version: str = "1.0"
    pick_id: str = Field(min_length=1, max_length=255)
    commerce_id: str = Field(min_length=1, max_length=255)
    selected_at: datetime
    source: ActivePickSource

    @model_validator(mode="after")
    def validate_selected_at(self) -> "ActivePickReference":
        if self.selected_at.tzinfo is None:
            raise ValueError("selected_at must include a timezone")
        return self


class StateReadStatus(StrEnum):
    FOUND = "found"
    MISSING = "missing"
    UNAVAILABLE = "unavailable"


class ActivePickRead(ContractModel):
    status: StateReadStatus
    reference: ActivePickReference | None = None

    @model_validator(mode="after")
    def validate_shape(self) -> "ActivePickRead":
        if (self.status is StateReadStatus.FOUND) != (self.reference is not None):
            raise ValueError("only found active-pick reads contain a reference")
        return self


class StateWriteResult(ContractModel):
    success: bool
    state_available: bool

    @model_validator(mode="after")
    def validate_shape(self) -> "StateWriteResult":
        if self.success and not self.state_available:
            raise ValueError("successful writes require available state")
        return self


class ActivePickResolutionStatus(StrEnum):
    CONFIRMED = "confirmed"
    MISSING = "missing"
    STALE = "stale"
    STATE_UNAVAILABLE = "state_unavailable"
    UPSTREAM_UNAVAILABLE = "upstream_unavailable"


class ActivePickResolution(ContractModel):
    status: ActivePickResolutionStatus
    pick: AvailablePick | None = None
    source: ActivePickSource | None = None
    context_persisted: bool = False
    error_code: ToolErrorCode | None = None

    @model_validator(mode="after")
    def validate_shape(self) -> "ActivePickResolution":
        confirmed = self.status is ActivePickResolutionStatus.CONFIRMED
        if confirmed != (self.pick is not None and self.source is not None):
            raise ValueError("only confirmed resolutions contain pick evidence and source")
        if confirmed and self.error_code is not None:
            raise ValueError("confirmed resolutions cannot contain an error")
        return self


class AsyncKeyValueStore(Protocol):
    def get(self, name: str) -> Awaitable[str | bytes | None]: ...

    def set(self, name: str, value: str, *, ex: int) -> Awaitable[bool | None]: ...

    def delete(self, *names: str) -> Awaitable[int]: ...

    def aclose(self) -> Awaitable[None]: ...


class ActivePickReader(Protocol):
    async def get_available_pick(self, pick_id: str) -> AvailablePick: ...


def conversation_scope_digest(scope: ConversationScope) -> str:
    identity = "\x1f".join(
        (scope.channel.value, scope.channel_account_id, scope.conversation_id)
    )
    return hashlib.sha256(identity.encode()).hexdigest()


class RedisActivePickStore:
    key_prefix = "piki:v1:conversation"

    def __init__(self, redis: AsyncKeyValueStore, *, ttl_seconds: int) -> None:
        if ttl_seconds < 1:
            raise ValueError("active-pick TTL must be positive")
        self._redis = redis
        self._ttl_seconds = ttl_seconds

    async def close(self) -> None:
        await self._redis.aclose()

    @classmethod
    def key_for(cls, scope: ConversationScope) -> str:
        return f"{cls.key_prefix}:{conversation_scope_digest(scope)}:active-pick"

    async def set(
        self, scope: ConversationScope, reference: ActivePickReference
    ) -> StateWriteResult:
        try:
            stored = await self._redis.set(
                self.key_for(scope), reference.model_dump_json(), ex=self._ttl_seconds
            )
        except RedisError:
            return StateWriteResult(success=False, state_available=False)
        return StateWriteResult(success=bool(stored), state_available=True)

    async def get(self, scope: ConversationScope) -> ActivePickRead:
        try:
            payload = await self._redis.get(self.key_for(scope))
        except RedisError:
            return ActivePickRead(status=StateReadStatus.UNAVAILABLE)
        if payload is None:
            return ActivePickRead(status=StateReadStatus.MISSING)
        try:
            reference = ActivePickReference.model_validate_json(payload)
        except ValueError:
            await self.clear(scope)
            return ActivePickRead(status=StateReadStatus.UNAVAILABLE)
        return ActivePickRead(status=StateReadStatus.FOUND, reference=reference)

    async def clear(self, scope: ConversationScope) -> StateWriteResult:
        try:
            await self._redis.delete(self.key_for(scope))
        except RedisError:
            return StateWriteResult(success=False, state_available=False)
        return StateWriteResult(success=True, state_available=True)


class ActivePickService:
    def __init__(self, store: RedisActivePickStore, client: ActivePickReader) -> None:
        self._store = store
        self._client = client

    async def remember(
        self, scope: ConversationScope, pick: AvailablePick, source: ActivePickSource
    ) -> StateWriteResult:
        reference = ActivePickReference(
            pick_id=pick.id,
            commerce_id=pick.commerce.id,
            selected_at=datetime.now(UTC),
            source=source,
        )
        return await self._store.set(scope, reference)

    async def resolve(
        self, scope: ConversationScope, *, explicit_pick_id: str | None = None
    ) -> ActivePickResolution:
        reference: ActivePickReference | None = None
        source = ActivePickSource.EXPLICIT_REFERENCE
        if explicit_pick_id is None:
            active = await self._store.get(scope)
            if active.status is StateReadStatus.UNAVAILABLE:
                return ActivePickResolution(
                    status=ActivePickResolutionStatus.STATE_UNAVAILABLE
                )
            if active.status is StateReadStatus.MISSING:
                return ActivePickResolution(status=ActivePickResolutionStatus.MISSING)
            reference = active.reference
            if reference is None:
                raise AssertionError("found active pick must contain a reference")
            pick_id = reference.pick_id
            source = reference.source
        else:
            pick_id = explicit_pick_id.strip()
            if not pick_id:
                return ActivePickResolution(status=ActivePickResolutionStatus.MISSING)

        try:
            pick = await self._client.get_available_pick(pick_id)
        except BuenPickClientError as error:
            if error.code is ToolErrorCode.NOT_FOUND:
                if reference is not None:
                    await self._store.clear(scope)
                return ActivePickResolution(
                    status=ActivePickResolutionStatus.STALE,
                    error_code=error.code,
                )
            return ActivePickResolution(
                status=ActivePickResolutionStatus.UPSTREAM_UNAVAILABLE,
                error_code=error.code,
            )

        persisted = True
        if explicit_pick_id is not None:
            write = await self.remember(scope, pick, source)
            persisted = write.success
        return ActivePickResolution(
            status=ActivePickResolutionStatus.CONFIRMED,
            pick=pick,
            source=source,
            context_persisted=persisted,
        )


def create_active_pick_store(settings: Settings) -> RedisActivePickStore:
    redis = cast(
        AsyncKeyValueStore,
        Redis.from_url(settings.redis_url, decode_responses=True),
    )
    return RedisActivePickStore(redis, ttl_seconds=settings.active_pick_ttl_seconds)
