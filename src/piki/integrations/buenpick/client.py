import asyncio
from collections.abc import Awaitable, Callable
from typing import cast
from urllib.parse import quote, urlparse

import httpx
from pydantic import BaseModel, SecretStr, ValidationError

from piki.core.config import Settings
from piki.domain.contracts import ToolErrorCode
from piki.integrations.buenpick.models import (
    AvailablePick,
    Commerce,
    CustomerOrder,
    PickSearchResponse,
)

Sleep = Callable[[float], Awaitable[None]]


class BuenPickClientError(Exception):
    def __init__(
        self,
        *,
        code: ToolErrorCode,
        user_safe_message: str,
        status_code: int | None = None,
    ) -> None:
        super().__init__(code.value)
        self.code = code
        self.user_safe_message = user_safe_message
        self.status_code = status_code


class BuenPickConfigurationError(ValueError):
    pass


class CheckoutDisabledError(RuntimeError):
    pass


class BuenPickClient:
    production_host = "api.buenpick.com.ar"

    def __init__(
        self,
        *,
        base_url: str,
        token: SecretStr,
        timeout_seconds: float = 5.0,
        max_attempts: int = 3,
        allow_production: bool = False,
        transport: httpx.AsyncBaseTransport | None = None,
        sleep: Sleep = asyncio.sleep,
    ) -> None:
        host = urlparse(base_url).hostname
        if host == self.production_host and not allow_production:
            raise BuenPickConfigurationError("production BuenPick access is disabled")
        if not token.get_secret_value().strip():
            raise BuenPickConfigurationError("BuenPick token is required")
        if max_attempts < 1:
            raise BuenPickConfigurationError("max_attempts must be at least one")

        normalized_base_url = f"{base_url.rstrip('/')}/"
        self._max_attempts = max_attempts
        self._sleep = sleep
        self._client = httpx.AsyncClient(
            base_url=normalized_base_url,
            headers={
                "Authorization": f"Bearer {token.get_secret_value()}",
                "Accept": "application/json",
                "User-Agent": "piki/0.1",
            },
            timeout=httpx.Timeout(timeout_seconds),
            transport=transport,
        )

    async def __aenter__(self) -> "BuenPickClient":
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.close()

    async def close(self) -> None:
        await self._client.aclose()

    async def _request[ModelT: BaseModel](
        self,
        path: str,
        model: type[ModelT],
        params: dict[str, str] | None = None,
    ) -> ModelT:
        for attempt in range(1, self._max_attempts + 1):
            try:
                response = await self._client.get(path, params=params)
            except httpx.TimeoutException as error:
                if attempt < self._max_attempts:
                    await self._sleep(0.1 * (2 ** (attempt - 1)))
                    continue
                raise BuenPickClientError(
                    code=ToolErrorCode.TIMEOUT,
                    user_safe_message="No pude confirmar la informacion con BuenPick a tiempo.",
                ) from error
            except httpx.RequestError as error:
                raise BuenPickClientError(
                    code=ToolErrorCode.UPSTREAM_UNAVAILABLE,
                    user_safe_message="BuenPick no esta disponible en este momento.",
                ) from error

            if response.status_code in {429, 500, 503} and attempt < self._max_attempts:
                await self._sleep(0.1 * (2 ** (attempt - 1)))
                continue
            if response.is_error:
                raise self._map_http_error(response.status_code)

            try:
                payload = response.json()
                return model.model_validate(payload)
            except (ValueError, ValidationError) as error:
                raise BuenPickClientError(
                    code=ToolErrorCode.INTERNAL_ERROR,
                    user_safe_message="BuenPick devolvio una respuesta que no pude validar.",
                ) from error

        raise AssertionError("request loop exhausted unexpectedly")

    @staticmethod
    def _map_http_error(status_code: int) -> BuenPickClientError:
        if status_code == 400:
            return BuenPickClientError(
                code=ToolErrorCode.BAD_REQUEST,
                user_safe_message="La consulta enviada a BuenPick no es valida.",
                status_code=status_code,
            )
        if status_code == 401:
            return BuenPickClientError(
                code=ToolErrorCode.UNAUTHORIZED,
                user_safe_message="No pude validar el acceso o la pertenencia del recurso.",
                status_code=status_code,
            )
        if status_code == 404:
            return BuenPickClientError(
                code=ToolErrorCode.NOT_FOUND,
                user_safe_message="No pude confirmar que el recurso siga disponible.",
                status_code=status_code,
            )
        if status_code == 429:
            return BuenPickClientError(
                code=ToolErrorCode.RATE_LIMITED,
                user_safe_message=(
                    "BuenPick esta recibiendo muchas consultas. "
                    "Intenta nuevamente en breve."
                ),
                status_code=status_code,
            )
        return BuenPickClientError(
            code=ToolErrorCode.UPSTREAM_UNAVAILABLE,
            user_safe_message="BuenPick no esta disponible en este momento.",
            status_code=status_code,
        )

    async def search_available_picks(
        self, query: str | None = None, commerce_id: str | None = None
    ) -> PickSearchResponse:
        params = {}
        if query and query.strip():
            params["q"] = query.strip()
        if commerce_id and commerce_id.strip():
            params["commerce_id"] = commerce_id.strip()
        return await self._request("picks/search", PickSearchResponse, params=params)

    async def get_available_pick(self, pick_id: str) -> AvailablePick:
        return await self._request(f"picks/{quote(pick_id, safe='')}", AvailablePick)

    async def get_commerce(self, commerce_id: str) -> Commerce:
        return await self._request(f"commerces/{quote(commerce_id, safe='')}", Commerce)

    async def get_customer_order(
        self,
        order_id: str,
        *,
        customer_phone: str | None = None,
        customer_reference: str | None = None,
    ) -> CustomerOrder:
        provided = [
            bool(customer_phone and customer_phone.strip()),
            bool(customer_reference and customer_reference.strip()),
        ]
        if sum(provided) != 1:
            raise BuenPickClientError(
                code=ToolErrorCode.BAD_REQUEST,
                user_safe_message="La orden requiere una unica prueba de pertenencia.",
            )
        params = (
            {"customer_phone": customer_phone.strip()}
            if customer_phone
            else {"customer_reference": cast(str, customer_reference).strip()}
        )
        return await self._request(
            f"orders/{quote(order_id, safe='')}", CustomerOrder, params=params
        )

    async def create_checkout_session(self) -> None:
        raise CheckoutDisabledError(
            "Piki checkout is disabled; use the confirmed pick public_url instead"
        )


def create_buenpick_client(
    settings: Settings,
    *,
    transport: httpx.AsyncBaseTransport | None = None,
    sleep: Sleep = asyncio.sleep,
) -> BuenPickClient:
    token = settings.resolved_buenpick_internal_api_token
    if token is None:
        raise BuenPickConfigurationError("BuenPick token is required")
    return BuenPickClient(
        base_url=settings.buenpick_internal_api_base_url,
        token=token,
        timeout_seconds=settings.buenpick_timeout_seconds,
        max_attempts=settings.buenpick_max_attempts,
        allow_production=settings.buenpick_allow_production,
        transport=transport,
        sleep=sleep,
    )
