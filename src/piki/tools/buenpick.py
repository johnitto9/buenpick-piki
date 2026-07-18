import time
from collections.abc import Awaitable, Callable
from typing import Protocol

from pydantic import HttpUrl

from piki.domain.contracts import ContractModel, ToolErrorCode, ToolResult
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
)


class BuenPickReader(Protocol):
    async def search_available_picks(
        self, query: str | None = None, commerce_id: str | None = None
    ) -> PickSearchResponse: ...

    async def get_available_pick(self, pick_id: str) -> AvailablePick: ...

    async def get_commerce(self, commerce_id: str) -> Commerce: ...

    async def get_customer_order(
        self,
        order_id: str,
        *,
        customer_phone: str | None = None,
        customer_reference: str | None = None,
    ) -> CustomerOrder: ...


class PickImageEvidence(ContractModel):
    pick_id: str
    title: str
    image_url: HttpUrl


class BuenPickTools:
    def __init__(
        self,
        client: BuenPickReader,
        observer: LifecycleObserver | None = None,
    ) -> None:
        self._client = client
        self._observer = observer or LifecycleObserver()

    async def _run[DataT](
        self,
        trace_id: str,
        tool_name: str,
        operation: Callable[[], Awaitable[DataT]],
    ) -> ToolResult[DataT]:
        started = time.monotonic()
        observed_at = self._observer.started_at()
        self._observer.emit(
            LifecycleEvent.TOOL_STARTED,
            trace_id=trace_id,
            component=tool_name,
            outcome=EventOutcome.STARTED,
        )
        try:
            data = await operation()
            self._observer.emit(
                LifecycleEvent.TOOL_FINISHED,
                trace_id=trace_id,
                component=tool_name,
                outcome=EventOutcome.SUCCEEDED,
                started_at=observed_at,
            )
            return ToolResult[DataT](
                success=True,
                data=data,
                latency_ms=int((time.monotonic() - started) * 1000),
                trace_id=trace_id,
            )
        except BuenPickClientError as error:
            self._observer.emit(
                LifecycleEvent.TOOL_FINISHED,
                trace_id=trace_id,
                component=tool_name,
                outcome=EventOutcome.FAILED,
                started_at=observed_at,
                error_code=error.code.value,
            )
            return ToolResult[DataT](
                success=False,
                error_code=error.code,
                user_safe_message=error.user_safe_message,
                latency_ms=int((time.monotonic() - started) * 1000),
                trace_id=trace_id,
            )

    async def search_available_picks(
        self, *, query: str | None, commerce_id: str | None, trace_id: str
    ) -> ToolResult[PickSearchResponse]:
        return await self._run(
            trace_id,
            "search_available_picks",
            lambda: self._client.search_available_picks(query, commerce_id),
        )

    async def get_available_pick(
        self, *, pick_id: str, trace_id: str
    ) -> ToolResult[AvailablePick]:
        return await self._run(
            trace_id,
            "get_available_pick",
            lambda: self._client.get_available_pick(pick_id),
        )

    async def get_commerce(self, *, commerce_id: str, trace_id: str) -> ToolResult[Commerce]:
        return await self._run(
            trace_id,
            "get_commerce",
            lambda: self._client.get_commerce(commerce_id),
        )

    async def get_customer_order(
        self,
        *,
        order_id: str,
        customer_phone: str | None,
        customer_reference: str | None,
        trace_id: str,
    ) -> ToolResult[CustomerOrder]:
        return await self._run(
            trace_id,
            "get_customer_order",
            lambda: self._client.get_customer_order(
                order_id,
                customer_phone=customer_phone,
                customer_reference=customer_reference,
            ),
        )

    async def get_pick_image(
        self, *, pick_id: str, trace_id: str
    ) -> ToolResult[PickImageEvidence]:
        async def collect() -> PickImageEvidence:
            pick = await self._client.get_available_pick(pick_id)
            image_url = pick.images[0] if pick.images else pick.image_url
            if image_url is None:
                raise BuenPickClientError(
                    code=ToolErrorCode.NOT_FOUND,
                    user_safe_message="BuenPick no tiene una imagen disponible para este pick.",
                )
            return PickImageEvidence(pick_id=pick.id, title=pick.title, image_url=image_url)

        return await self._run(trace_id, "get_pick_image", collect)
