from datetime import UTC, datetime
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from piki.conversation.service import (
    ConversationBusyError,
    ConversationOrchestrator,
    ConversationReply,
)
from piki.core.config import Settings
from piki.domain.contracts import Channel, InboundMessage, MessageKind


class ApiModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ChatMessageRequest(ApiModel):
    conversation_id: str = Field(min_length=1, max_length=255)
    message: str = Field(min_length=1, max_length=4096)
    message_id: str | None = Field(default=None, min_length=1, max_length=255)


class ChatRuntimeStatus(ApiModel):
    enabled: bool
    llm_provider: str | None
    llm_model: str | None
    buenpick_api_configured: bool
    meta_ingress_enabled: bool


class ChatHistoryMessage(ApiModel):
    role: Literal["user", "assistant"]
    text: str = Field(min_length=1, max_length=4096)
    created_at: datetime


def create_chat_router(
    *,
    settings: Settings,
    orchestrator: ConversationOrchestrator | None,
) -> APIRouter:
    router = APIRouter(prefix="/api/chat", tags=["local-chat"])

    @router.get("/status", response_model=ChatRuntimeStatus)
    async def runtime_status() -> ChatRuntimeStatus:
        return ChatRuntimeStatus(
            enabled=orchestrator is not None,
            llm_provider=settings.llm_provider,
            llm_model=settings.llm_model,
            buenpick_api_configured=(
                settings.resolved_buenpick_internal_api_token is not None
            ),
            meta_ingress_enabled=settings.meta_ingress_enabled,
        )

    @router.post("/messages", response_model=ConversationReply)
    async def send_message(request: ChatMessageRequest) -> ConversationReply:
        if orchestrator is None:
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "conversation runtime is not configured",
            )
        message_id = request.message_id or f"web-{uuid4()}"
        inbound = InboundMessage(
            message_id=message_id,
            channel=Channel.WEB,
            conversation_id=request.conversation_id,
            sender_id=request.conversation_id,
            kind=MessageKind.TEXT,
            text=request.message,
            received_at=datetime.now(UTC),
        )
        try:
            return await orchestrator.respond(
                inbound,
                channel_account_id="piki-local-console",
            )
        except ConversationBusyError as error:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "conversation is already being processed",
            ) from error

    @router.get(
        "/conversations/{conversation_id}/messages",
        response_model=tuple[ChatHistoryMessage, ...],
    )
    async def conversation_history(
        conversation_id: str,
    ) -> tuple[ChatHistoryMessage, ...]:
        if orchestrator is None:
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "conversation runtime is not configured",
            )
        history = await orchestrator.history(
            channel=Channel.WEB,
            channel_account_id="piki-local-console",
            conversation_id=conversation_id,
        )
        return tuple(
            ChatHistoryMessage(
                role="assistant" if item.direction == "outbound" else "user",
                text=item.content_text,
                created_at=item.created_at,
            )
            for item in history
            if item.content_text
        )

    return router
