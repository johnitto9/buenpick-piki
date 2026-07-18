from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from piki.api.app import create_app
from piki.api.health import HealthReport, HealthStatus, ProbeResult
from piki.conversation.service import ConversationIntent, ConversationReply
from piki.core.config import Environment, Settings
from piki.domain.contracts import InboundMessage


class StubReadiness:
    async def check(self) -> HealthReport:
        return HealthReport(
            status=HealthStatus.OK,
            service="Piki",
            version="test",
            checks={"test": ProbeResult(status=HealthStatus.OK, detail="ready")},
        )

    async def close(self) -> None:
        return None


class StubOrchestrator:
    def __init__(self) -> None:
        self.messages: list[tuple[str, str]] = []

    async def respond(
        self, message: InboundMessage, *, channel_account_id: str
    ) -> ConversationReply:
        text = message.text
        assert text is not None
        self.messages.append((channel_account_id, text))
        return ConversationReply(
            conversation_id=UUID("00000000-0000-0000-0000-000000000123"),
            text="Hola, soy Piki. ¿Qué alimento querés rescatar?",
            intent=ConversationIntent.GREETING,
            trace_id="conversation:web-test-message",
        )


def test_chat_api_and_console_are_same_origin_and_operational() -> None:
    orchestrator = StubOrchestrator()
    settings = Settings(
        environment=Environment.TEST,
        local_console_enabled=True,
        llm_provider="nvidia_nim",
        llm_model="z-ai/glm-5.2",
    )
    app = create_app(
        settings=settings,
        readiness=StubReadiness(),  # type: ignore[arg-type]
        conversation_orchestrator=orchestrator,  # type: ignore[arg-type]
    )
    with TestClient(app) as client:
        console = client.get("/console")
        status = client.get("/api/chat/status")
        response = client.post(
            "/api/chat/messages",
            json={
                "conversation_id": f"web-{uuid4()}",
                "message_id": "web-test-message",
                "message": "Hola Piki",
            },
        )
        styles = client.get("/console/assets/app.css")

    assert console.status_code == 200
    assert "Conversación local" in console.text
    assert styles.headers["content-type"].startswith("text/css")
    assert status.json() == {
        "enabled": True,
        "llm_provider": "nvidia_nim",
        "llm_model": "z-ai/glm-5.2",
        "buenpick_api_configured": False,
        "meta_ingress_enabled": False,
    }
    assert response.status_code == 200
    assert response.json()["intent"] == "greeting"
    assert "Piki" in response.json()["text"]
    assert orchestrator.messages == [("piki-local-console", "Hola Piki")]


def test_chat_is_explicitly_unavailable_without_runtime() -> None:
    settings = Settings(environment=Environment.TEST, local_console_enabled=True)
    with TestClient(
        create_app(settings=settings, readiness=StubReadiness())  # type: ignore[arg-type]
    ) as client:
        status_response = client.get("/api/chat/status")
        message_response = client.post(
            "/api/chat/messages",
            json={"conversation_id": "web-disabled", "message": "Hola"},
        )

    assert status_response.json()["enabled"] is False
    assert message_response.status_code == 503
