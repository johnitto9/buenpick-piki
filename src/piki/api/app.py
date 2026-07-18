from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import cast

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from piki.api.chat import create_chat_router
from piki.api.health import (
    HealthReport,
    HealthStatus,
    InfrastructureReadiness,
    ProbeResult,
    Readiness,
)
from piki.api.meta_webhook import create_meta_webhook_router
from piki.conversation.service import (
    ConversationOrchestrator,
    create_conversation_orchestrator,
)
from piki.core.config import Settings, get_settings
from piki.core.logging import configure_logging
from piki.integrations.meta.ingress import (
    DefaultMetaWebhookIngress,
    create_default_meta_ingress,
)
from piki.integrations.meta.webhook import MetaWebhookIngress
from piki.web.router import create_console_router


def create_app(
    settings: Settings | None = None,
    readiness: Readiness | None = None,
    meta_ingress: MetaWebhookIngress | None = None,
    conversation_orchestrator: ConversationOrchestrator | None = None,
) -> FastAPI:
    runtime_settings = settings or get_settings()
    runtime_readiness = readiness or InfrastructureReadiness(
        service=runtime_settings.app_name,
        version=runtime_settings.app_version,
        database_url=runtime_settings.resolved_database_url,
        redis_url=runtime_settings.redis_url,
        timeout_seconds=runtime_settings.readiness_timeout_seconds,
    )
    owned_meta_ingress: DefaultMetaWebhookIngress | None = None
    runtime_meta_ingress = meta_ingress
    if runtime_settings.meta_ingress_enabled and runtime_meta_ingress is None:
        owned_meta_ingress = create_default_meta_ingress(runtime_settings)
        runtime_meta_ingress = owned_meta_ingress
    owned_conversation_orchestrator: ConversationOrchestrator | None = None
    runtime_conversation_orchestrator = conversation_orchestrator
    if (
        runtime_settings.conversation_enabled
        and runtime_settings.local_console_enabled
        and runtime_conversation_orchestrator is None
    ):
        owned_conversation_orchestrator = create_conversation_orchestrator(
            runtime_settings
        )
        runtime_conversation_orchestrator = owned_conversation_orchestrator

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        configure_logging(runtime_settings.log_level)
        yield
        if owned_meta_ingress is not None:
            await owned_meta_ingress.close()
        if owned_conversation_orchestrator is not None:
            await owned_conversation_orchestrator.close()
        await runtime_readiness.close()

    app = FastAPI(
        title=runtime_settings.app_name,
        version=runtime_settings.app_version,
        docs_url=None if runtime_settings.is_production else "/docs",
        redoc_url=None,
        lifespan=lifespan,
    )
    app.state.settings = runtime_settings
    app.state.readiness = runtime_readiness
    app.include_router(
        create_meta_webhook_router(
            verify_token=runtime_settings.resolved_meta_webhook_verify_token,
            app_secret=runtime_settings.resolved_meta_app_secret,
            expected_waba_id=runtime_settings.meta_waba_id,
            expected_phone_number_id=runtime_settings.meta_phone_number_id,
            ingress=runtime_meta_ingress,
        )
    )
    if runtime_settings.local_console_enabled:
        app.include_router(
            create_chat_router(
                settings=runtime_settings,
                orchestrator=runtime_conversation_orchestrator,
            )
        )
        app.include_router(create_console_router())

    @app.get("/health", response_model=HealthReport, tags=["operations"])
    @app.get("/health/live", response_model=HealthReport, tags=["operations"])
    async def live() -> HealthReport:
        return HealthReport(
            status=HealthStatus.OK,
            service=runtime_settings.app_name,
            version=runtime_settings.app_version,
            checks={"process": ProbeResult(status=HealthStatus.OK, detail="running")},
        )

    @app.get(
        "/health/ready",
        response_model=HealthReport,
        responses={status.HTTP_503_SERVICE_UNAVAILABLE: {"model": HealthReport}},
        tags=["operations"],
    )
    async def ready(request: Request) -> HealthReport | JSONResponse:
        checker = cast(Readiness, request.app.state.readiness)
        report = await checker.check()
        if report.status is HealthStatus.DEGRADED:
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content=report.model_dump(mode="json"),
            )
        return report

    return app
