import asyncio
from collections.abc import Awaitable, Callable
from enum import StrEnum
from typing import Protocol, cast

from pydantic import BaseModel, ConfigDict
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine


class HealthStatus(StrEnum):
    OK = "ok"
    DEGRADED = "degraded"


class ProbeResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    status: HealthStatus
    detail: str


class HealthReport(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    status: HealthStatus
    service: str
    version: str
    checks: dict[str, ProbeResult]


class Readiness(Protocol):
    async def check(self) -> HealthReport: ...

    async def close(self) -> None: ...


class InfrastructureReadiness:
    def __init__(
        self,
        *,
        service: str,
        version: str,
        database_url: str,
        redis_url: str,
        timeout_seconds: float,
    ) -> None:
        self._service = service
        self._version = version
        self._timeout_seconds = timeout_seconds
        self._engine: AsyncEngine = create_async_engine(database_url, pool_pre_ping=True)
        self._redis = Redis.from_url(redis_url, decode_responses=True)

    async def _probe(
        self, name: str, operation: Callable[[], Awaitable[None]]
    ) -> tuple[str, ProbeResult]:
        try:
            async with asyncio.timeout(self._timeout_seconds):
                await operation()
            return name, ProbeResult(status=HealthStatus.OK, detail="reachable")
        except Exception:
            return name, ProbeResult(status=HealthStatus.DEGRADED, detail="unreachable")

    async def _database_ping(self) -> None:
        async with self._engine.connect() as connection:
            await connection.execute(text("SELECT 1"))

    async def _redis_ping(self) -> None:
        await cast(Awaitable[bool], self._redis.ping())

    async def check(self) -> HealthReport:
        probe_pairs = await asyncio.gather(
            self._probe("postgres", self._database_ping),
            self._probe("redis", self._redis_ping),
        )
        checks = dict(probe_pairs)
        status = (
            HealthStatus.OK
            if all(result.status is HealthStatus.OK for result in checks.values())
            else HealthStatus.DEGRADED
        )
        return HealthReport(
            status=status,
            service=self._service,
            version=self._version,
            checks=checks,
        )

    async def close(self) -> None:
        await self._redis.aclose()
        await self._engine.dispose()
