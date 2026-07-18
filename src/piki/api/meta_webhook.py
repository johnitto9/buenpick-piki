import json

from fastapi import APIRouter, HTTPException, Query, Request, Response, status
from pydantic import SecretStr

from piki.integrations.meta.webhook import (
    MetaIngressRetryableError,
    MetaWebhookError,
    MetaWebhookIngress,
    WebhookIngestResult,
    normalize_webhook,
    verify_challenge,
    verify_signature,
)


def create_meta_webhook_router(
    *,
    verify_token: SecretStr | None,
    app_secret: SecretStr | None,
    expected_waba_id: str | None,
    expected_phone_number_id: str | None,
    ingress: MetaWebhookIngress | None,
) -> APIRouter:
    router = APIRouter(prefix="/webhooks/meta/whatsapp", tags=["meta-webhook"])

    @router.get("")
    async def challenge(
        mode: str | None = Query(default=None, alias="hub.mode"),
        provided_token: str | None = Query(default=None, alias="hub.verify_token"),
        challenge_value: str | None = Query(default=None, alias="hub.challenge"),
    ) -> Response:
        if verify_token is None:
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "webhook not configured")
        if challenge_value is None or not verify_challenge(
            mode=mode,
            provided_token=provided_token,
            expected_token=verify_token,
        ):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "webhook verification failed")
        return Response(content=challenge_value, media_type="text/plain")

    @router.post("", response_model=WebhookIngestResult)
    async def receive(request: Request) -> WebhookIngestResult:
        if app_secret is None or ingress is None:
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "webhook not ready")
        raw_body = await request.body()
        if not verify_signature(
            raw_body,
            request.headers.get("X-Hub-Signature-256"),
            app_secret,
        ):
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid webhook signature")
        try:
            payload = json.loads(raw_body)
            if not isinstance(payload, dict):
                raise MetaWebhookError("webhook payload must be an object")
            events = normalize_webhook(
                payload,
                expected_waba_id=expected_waba_id,
                expected_phone_number_id=expected_phone_number_id,
            )
        except (json.JSONDecodeError, MetaWebhookError) as error:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, "invalid webhook payload"
            ) from error
        try:
            return await ingress.ingest(events)
        except MetaIngressRetryableError as error:
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "webhook ingress temporarily unavailable",
            ) from error

    return router
