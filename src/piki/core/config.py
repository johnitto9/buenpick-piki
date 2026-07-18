from enum import StrEnum
from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(StrEnum):
    DEVELOPMENT = "development"
    TEST = "test"
    PRODUCTION = "production"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="PIKI_",
        extra="ignore",
    )

    app_name: str = "Piki"
    app_version: str = "0.1.0"
    environment: Environment = Environment.DEVELOPMENT
    host: str = "0.0.0.0"  # noqa: S104 - required inside the container network
    port: int = Field(default=8000, ge=1, le=65535)
    log_level: str = "INFO"
    database_url: str = "postgresql+psycopg://piki:piki@postgres:5432/piki"
    database_url_file: Path | None = None
    redis_url: str = "redis://redis:6379/0"
    active_pick_ttl_seconds: int = Field(default=1800, ge=60, le=86400)
    conversation_lock_ttl_seconds: int = Field(default=30, ge=5, le=300)
    message_dedup_ttl_seconds: int = Field(default=604800, ge=3600, le=2592000)
    pending_action_ttl_seconds: int = Field(default=900, ge=60, le=86400)
    llm_provider: str | None = None
    llm_model: str | None = None
    llm_api_key: SecretStr | None = None
    llm_api_key_file: Path | None = None
    llm_base_url: str = "https://api.openai.com/v1"
    llm_timeout_seconds: float = Field(default=15.0, gt=0, le=60)
    llm_max_attempts: int = Field(default=2, ge=1, le=5)
    llm_max_output_tokens: int = Field(default=500, ge=64, le=4096)
    meta_app_id: str | None = None
    meta_app_secret: SecretStr | None = None
    meta_app_secret_file: Path | None = None
    meta_waba_id: str | None = None
    meta_phone_number_id: str | None = None
    meta_access_token: SecretStr | None = None
    meta_access_token_file: Path | None = None
    meta_webhook_verify_token: SecretStr | None = None
    meta_webhook_verify_token_file: Path | None = None
    meta_graph_api_version: str | None = None
    meta_graph_base_url: str = "https://graph.facebook.com"
    meta_delivery_timeout_seconds: float = Field(default=10.0, gt=0, le=60)
    meta_ingress_enabled: bool = False
    conversation_enabled: bool = False
    conversation_worker_enabled: bool = False
    conversation_worker_poll_seconds: float = Field(default=1.0, ge=0.1, le=30)
    conversation_worker_claim_timeout_seconds: int = Field(default=120, ge=30, le=3600)
    conversation_worker_max_attempts: int = Field(default=3, ge=1, le=10)
    local_console_enabled: bool = False
    readiness_timeout_seconds: float = Field(default=1.5, gt=0, le=10)
    worker_heartbeat_path: str = "/var/run/piki/worker-ready"
    worker_heartbeat_seconds: float = Field(default=5.0, ge=1, le=60)
    buenpick_internal_api_base_url: str = "http://buenpick-mock.invalid/internal/v1"
    buenpick_internal_api_token: SecretStr | None = None
    buenpick_internal_api_token_file: Path | None = None
    buenpick_timeout_seconds: float = Field(default=5.0, gt=0, le=30)
    buenpick_max_attempts: int = Field(default=3, ge=1, le=5)
    buenpick_allow_production: bool = False

    @field_validator(
        "llm_provider",
        "llm_model",
        "llm_api_key",
        "llm_api_key_file",
        "meta_app_id",
        "meta_app_secret",
        "meta_app_secret_file",
        "meta_waba_id",
        "meta_phone_number_id",
        "meta_access_token",
        "meta_access_token_file",
        "meta_webhook_verify_token",
        "meta_webhook_verify_token_file",
        "meta_graph_api_version",
        "buenpick_internal_api_token",
        "buenpick_internal_api_token_file",
        mode="before",
    )
    @classmethod
    def blank_optional_value(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @model_validator(mode="after")
    def validate_meta_ingress_configuration(self) -> "Settings":
        if self.meta_ingress_enabled:
            if self.resolved_meta_app_secret is None:
                raise ValueError("Meta ingress requires an app secret")
            if self.resolved_meta_webhook_verify_token is None:
                raise ValueError("Meta ingress requires a webhook verify token")
            if self.meta_waba_id is None:
                raise ValueError("Meta ingress requires a WABA ID")
            if self.meta_phone_number_id is None:
                raise ValueError("Meta ingress requires a phone number ID")
        if self.conversation_worker_enabled:
            if not self.conversation_enabled:
                raise ValueError("conversation worker requires conversation runtime")
            if self.resolved_meta_access_token is None:
                raise ValueError("conversation worker requires a Meta access token")
            if self.meta_phone_number_id is None:
                raise ValueError("conversation worker requires a Meta phone number ID")
            if self.meta_graph_api_version is None:
                raise ValueError("conversation worker requires a Meta Graph API version")
        return self

    @property
    def is_production(self) -> bool:
        return self.environment is Environment.PRODUCTION

    @property
    def resolved_database_url(self) -> str:
        if self.database_url_file is None:
            return self.database_url
        value = self.database_url_file.read_text(encoding="utf-8").strip()
        if not value:
            raise ValueError("database URL secret file is empty")
        return value

    @staticmethod
    def _resolved_secret(
        direct: SecretStr | None,
        secret_file: Path | None,
        *,
        name: str,
    ) -> SecretStr | None:
        if secret_file is None:
            return direct
        value = secret_file.read_text(encoding="utf-8").strip()
        if not value:
            raise ValueError(f"{name} secret file is empty")
        return SecretStr(value)

    @property
    def resolved_meta_app_secret(self) -> SecretStr | None:
        return self._resolved_secret(
            self.meta_app_secret,
            self.meta_app_secret_file,
            name="Meta app secret",
        )

    @property
    def resolved_llm_api_key(self) -> SecretStr | None:
        return self._resolved_secret(
            self.llm_api_key,
            self.llm_api_key_file,
            name="LLM API key",
        )

    @property
    def resolved_buenpick_internal_api_token(self) -> SecretStr | None:
        return self._resolved_secret(
            self.buenpick_internal_api_token,
            self.buenpick_internal_api_token_file,
            name="BuenPick Internal API token",
        )

    @property
    def resolved_meta_access_token(self) -> SecretStr | None:
        return self._resolved_secret(
            self.meta_access_token,
            self.meta_access_token_file,
            name="Meta access token",
        )

    @property
    def resolved_meta_webhook_verify_token(self) -> SecretStr | None:
        return self._resolved_secret(
            self.meta_webhook_verify_token,
            self.meta_webhook_verify_token_file,
            name="Meta webhook verify token",
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
