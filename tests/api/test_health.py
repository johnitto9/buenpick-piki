from uuid import uuid4

from fastapi.testclient import TestClient
from pydantic import SecretStr
from pytest import MonkeyPatch

from piki.api.app import create_app
from piki.api.health import HealthReport, HealthStatus, ProbeResult
from piki.core.config import Environment, Settings


class StubReadiness:
    def __init__(self, status: HealthStatus) -> None:
        self.status = status
        self.closed = False

    async def check(self) -> HealthReport:
        return HealthReport(
            status=self.status,
            service="Piki",
            version="test",
            checks={
                "postgres": ProbeResult(status=self.status, detail="test"),
                "redis": ProbeResult(status=self.status, detail="test"),
            },
        )

    async def close(self) -> None:
        self.closed = True


class StubOwnedMetaIngress:
    def __init__(self) -> None:
        self.closed = False

    async def close(self) -> None:
        self.closed = True


def client_for(status: HealthStatus) -> tuple[TestClient, StubReadiness]:
    readiness = StubReadiness(status)
    settings = Settings(environment=Environment.TEST, app_version="test")
    return TestClient(create_app(settings=settings, readiness=readiness)), readiness


def test_liveness_is_200_and_does_not_depend_on_infrastructure() -> None:
    client, _ = client_for(HealthStatus.DEGRADED)
    with client:
        response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["checks"]["process"]["detail"] == "running"


def test_readiness_is_200_when_all_dependencies_are_reachable() -> None:
    client, _ = client_for(HealthStatus.OK)
    with client:
        response = client.get("/health/ready")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_readiness_is_503_when_a_dependency_is_unreachable() -> None:
    client, _ = client_for(HealthStatus.DEGRADED)
    with client:
        response = client.get("/health/ready")
    assert response.status_code == 503
    assert response.json()["status"] == "degraded"


def test_lifespan_closes_readiness_resources() -> None:
    client, readiness = client_for(HealthStatus.OK)
    with client:
        pass
    assert readiness.closed is True


def test_lifespan_closes_application_owned_meta_ingress(
    monkeypatch: MonkeyPatch,
) -> None:
    readiness = StubReadiness(HealthStatus.OK)
    ingress = StubOwnedMetaIngress()
    app_secret = SecretStr(uuid4().hex)
    verify_token = SecretStr(uuid4().hex)
    settings = Settings(
        environment=Environment.TEST,
        meta_ingress_enabled=True,
        meta_app_secret=app_secret,
        meta_webhook_verify_token=verify_token,
    )
    monkeypatch.setattr(
        "piki.api.app.create_default_meta_ingress", lambda _: ingress
    )

    with TestClient(create_app(settings=settings, readiness=readiness)):
        pass

    assert ingress.closed is True
    assert readiness.closed is True


def test_production_disables_interactive_docs() -> None:
    readiness = StubReadiness(HealthStatus.OK)
    settings = Settings(environment=Environment.PRODUCTION)
    with TestClient(create_app(settings=settings, readiness=readiness)) as client:
        assert client.get("/docs").status_code == 404
