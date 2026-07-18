from typing import Any

import httpx
from pydantic import BaseModel, ConfigDict, SecretStr, ValidationError

from piki.core.config import Settings
from piki.domain.contracts import (
    CustomerServiceWindow,
    DeliveryKind,
    DeliveryRequest,
    DeliveryResult,
    DeliveryStatus,
)


class MetaResponseModel(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)


class MetaMessageIdentifier(MetaResponseModel):
    id: str


class MetaSendResponse(MetaResponseModel):
    messaging_product: str
    messages: tuple[MetaMessageIdentifier, ...]


class MetaDeliveryAdapter:
    def __init__(
        self,
        *,
        graph_base_url: str,
        graph_api_version: str,
        phone_number_id: str,
        access_token: SecretStr,
        timeout_seconds: float = 10.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        required = {
            "graph_api_version": graph_api_version,
            "phone_number_id": phone_number_id,
            "access_token": access_token.get_secret_value(),
        }
        if any(not value.strip() for value in required.values()):
            raise ValueError("Meta delivery configuration is incomplete")
        self._phone_number_id = phone_number_id.strip()
        self._client = httpx.AsyncClient(
            base_url=f"{graph_base_url.rstrip('/')}/{graph_api_version.strip().strip('/')}/",
            headers={
                "Authorization": f"Bearer {access_token.get_secret_value()}",
                "Content-Type": "application/json",
                "User-Agent": "piki/0.1",
            },
            timeout=httpx.Timeout(timeout_seconds),
            transport=transport,
        )

    async def __aenter__(self) -> "MetaDeliveryAdapter":
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.close()

    async def close(self) -> None:
        await self._client.aclose()

    async def send(self, request: DeliveryRequest) -> DeliveryResult:
        if (
            request.kind is not DeliveryKind.TEMPLATE
            and request.customer_service_window is not CustomerServiceWindow.OPEN
        ):
            return self._window_failure(request)
        body_or_error = self._build_body(request)
        if isinstance(body_or_error, DeliveryResult):
            return body_or_error
        try:
            response = await self._client.post(
                f"{self._phone_number_id}/messages",
                json=body_or_error,
            )
        except httpx.TimeoutException:
            return DeliveryResult(
                status=DeliveryStatus.UNKNOWN,
                error_code="META_TIMEOUT_UNCERTAIN",
                error_message="Meta no confirmó si aceptó el mensaje antes del timeout.",
                trace_id=request.trace_id,
            )
        except httpx.RequestError:
            return DeliveryResult(
                status=DeliveryStatus.UNKNOWN,
                error_code="META_NETWORK_UNCERTAIN",
                error_message="No se pudo confirmar el resultado del envío con Meta.",
                trace_id=request.trace_id,
            )

        if response.is_error:
            return self._rejected_result(response, request.trace_id)
        try:
            payload = MetaSendResponse.model_validate(response.json())
            provider_message_id = payload.messages[0].id
            if not provider_message_id.strip():
                raise ValueError("empty Meta message ID")
        except (ValueError, ValidationError, IndexError):
            return DeliveryResult(
                status=DeliveryStatus.UNKNOWN,
                error_code="META_INVALID_SUCCESS_RESPONSE",
                error_message="Meta respondió sin un identificador de mensaje válido.",
                trace_id=request.trace_id,
            )
        return DeliveryResult(
            status=DeliveryStatus.ACCEPTED,
            provider_message_id=provider_message_id,
            trace_id=request.trace_id,
            metadata={"messaging_product": payload.messaging_product},
        )

    @staticmethod
    def _build_body(request: DeliveryRequest) -> dict[str, Any] | DeliveryResult:
        body: dict[str, Any] = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": request.conversation_id,
        }
        if request.kind is DeliveryKind.TEXT:
            body.update(
                {
                    "type": "text",
                    "text": {"preview_url": False, "body": request.text},
                }
            )
        elif request.kind is DeliveryKind.IMAGE:
            if request.text and len(request.text) > 1024:
                return MetaDeliveryAdapter._local_failure(
                    request, "META_IMAGE_CAPTION_TOO_LONG"
                )
            image: dict[str, str] = {"link": str(request.media_url)}
            if request.text:
                image["caption"] = request.text
            body.update({"type": "image", "image": image})
        elif request.kind is DeliveryKind.INTERACTIVE:
            buttons = [
                {
                    "type": "reply",
                    "reply": {"id": option.id, "title": option.title},
                }
                for option in request.interactive_options
            ]
            body.update(
                {
                    "type": "interactive",
                    "interactive": {
                        "type": "button",
                        "body": {"text": request.text},
                        "action": {"buttons": buttons},
                    },
                }
            )
        elif request.kind is DeliveryKind.TEMPLATE:
            template: dict[str, Any] = {
                "name": request.template_name,
                "language": {"code": request.template_language},
            }
            if request.template_parameters:
                template["components"] = [
                    {
                        "type": "body",
                        "parameters": [
                            {"type": "text", "text": value}
                            for value in request.template_parameters
                        ],
                    }
                ]
            body.update({"type": "template", "template": template})
        return body

    @staticmethod
    def _local_failure(request: DeliveryRequest, code: str) -> DeliveryResult:
        return DeliveryResult(
            status=DeliveryStatus.FAILED,
            error_code=code,
            error_message="El mensaje no cumple el contrato de entrega de Meta.",
            trace_id=request.trace_id,
        )

    @staticmethod
    def _window_failure(request: DeliveryRequest) -> DeliveryResult:
        if request.customer_service_window is CustomerServiceWindow.CLOSED:
            code = "META_TEMPLATE_REQUIRED"
            message = "La ventana de atención está cerrada; se requiere un template aprobado."
        else:
            code = "META_WINDOW_UNCONFIRMED"
            message = "No se pudo confirmar la ventana de atención para el envío libre."
        return DeliveryResult(
            status=DeliveryStatus.FAILED,
            error_code=code,
            error_message=message,
            trace_id=request.trace_id,
        )

    @staticmethod
    def _rejected_result(response: httpx.Response, trace_id: str) -> DeliveryResult:
        error_code = f"META_HTTP_{response.status_code}"
        try:
            payload = response.json()
            meta_error = payload.get("error", {}) if isinstance(payload, dict) else {}
            if isinstance(meta_error, dict) and meta_error.get("code") is not None:
                error_code = f"META_{meta_error['code']}"
        except ValueError:
            pass
        return DeliveryResult(
            status=DeliveryStatus.FAILED,
            error_code=error_code,
            error_message="Meta rechazó el mensaje.",
            trace_id=trace_id,
            metadata={"http_status": response.status_code},
        )


def create_meta_delivery_adapter(
    settings: Settings,
    *,
    transport: httpx.AsyncBaseTransport | None = None,
) -> MetaDeliveryAdapter:
    if settings.meta_graph_api_version is None:
        raise ValueError("Meta Graph API version is required")
    if settings.meta_phone_number_id is None:
        raise ValueError("Meta phone number ID is required")
    access_token = settings.resolved_meta_access_token
    if access_token is None:
        raise ValueError("Meta access token is required")
    return MetaDeliveryAdapter(
        graph_base_url=settings.meta_graph_base_url,
        graph_api_version=settings.meta_graph_api_version,
        phone_number_id=settings.meta_phone_number_id,
        access_token=access_token,
        timeout_seconds=settings.meta_delivery_timeout_seconds,
        transport=transport,
    )
