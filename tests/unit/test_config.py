from pathlib import Path

import pytest
from pydantic import SecretStr, ValidationError

from piki.core.config import Environment, Settings


def test_settings_are_container_native() -> None:
    settings = Settings(environment=Environment.TEST)
    assert "postgres" in settings.database_url
    assert "redis" in settings.redis_url
    assert "C:\\" not in settings.database_url
    assert "/mnt/c/" not in settings.redis_url


def test_invalid_port_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Settings(port=70_000)


def test_database_url_can_come_from_a_secret_file(tmp_path: Path) -> None:
    secret_file = tmp_path / "database-url"
    secret_file.write_text("postgresql+psycopg://piki:secret@postgres:5432/piki\n")
    settings = Settings(database_url_file=secret_file)
    assert settings.resolved_database_url.endswith("@postgres:5432/piki")


def test_llm_and_buenpick_tokens_can_come_from_secret_files(tmp_path: Path) -> None:
    llm_file = tmp_path / "llm-key"
    buenpick_file = tmp_path / "buenpick-token"
    llm_file.write_text("llm-key-value\n", encoding="utf-8")
    buenpick_file.write_text("buenpick-token-value\n", encoding="utf-8")
    settings = Settings(
        llm_api_key_file=llm_file,
        buenpick_internal_api_token_file=buenpick_file,
    )

    assert settings.resolved_llm_api_key == SecretStr("llm-key-value")
    assert settings.resolved_buenpick_internal_api_token == SecretStr(
        "buenpick-token-value"
    )


def test_blank_optional_meta_values_are_normalized() -> None:
    blank_spaces = " " * 2
    blank_tab = chr(9)
    settings = Settings(
        meta_app_secret=blank_spaces,
        meta_access_token="",
        meta_webhook_verify_token=blank_tab,
    )

    assert settings.resolved_meta_app_secret is None
    assert settings.resolved_meta_access_token is None
    assert settings.resolved_meta_webhook_verify_token is None


def test_meta_secrets_can_come_from_files(tmp_path: Path) -> None:
    app_secret_file = tmp_path / "app-secret"
    access_token_file = tmp_path / "access-token"
    verify_token_file = tmp_path / "verify-token"
    app_secret_file.write_text("app-secret-value\n", encoding="utf-8")
    access_token_file.write_text("access-token-value\n", encoding="utf-8")
    verify_token_file.write_text("verify-token-value\n", encoding="utf-8")

    settings = Settings(
        meta_ingress_enabled=True,
        meta_app_secret_file=app_secret_file,
        meta_access_token_file=access_token_file,
        meta_webhook_verify_token_file=verify_token_file,
    )

    expected = {
        "app-secret-value",
        "access-token-value",
        "verify-token-value",
    }
    resolved = {
        value.get_secret_value()
        for value in (
            settings.resolved_meta_app_secret,
            settings.resolved_meta_access_token,
            settings.resolved_meta_webhook_verify_token,
        )
        if isinstance(value, SecretStr)
    }
    assert resolved == expected


def test_enabled_meta_ingress_requires_signing_and_verify_secrets() -> None:
    with pytest.raises(ValidationError, match="requires an app secret"):
        Settings(meta_ingress_enabled=True)

    configured_secret = SecretStr("configured")
    with pytest.raises(ValidationError, match="requires a webhook verify token"):
        Settings(meta_ingress_enabled=True, meta_app_secret=configured_secret)

    with pytest.raises(ValidationError, match="requires a WABA ID"):
        Settings(
            meta_ingress_enabled=True,
            meta_app_secret=configured_secret,
            meta_webhook_verify_token=configured_secret,
            meta_waba_id="",
            meta_phone_number_id="",
        )

    with pytest.raises(ValidationError, match="requires a phone number ID"):
        Settings(
            meta_ingress_enabled=True,
            meta_app_secret=configured_secret,
            meta_webhook_verify_token=configured_secret,
            meta_waba_id="waba-test",
            meta_phone_number_id="",
        )


def test_conversation_worker_requires_runtime_and_meta_delivery() -> None:
    with pytest.raises(ValidationError, match="requires conversation runtime"):
        Settings(conversation_worker_enabled=True)
    with pytest.raises(ValidationError, match="requires a Meta access token"):
        Settings(conversation_worker_enabled=True, conversation_enabled=True)
    with pytest.raises(ValidationError, match="requires a Meta phone number ID"):
        Settings(
            conversation_worker_enabled=True,
            conversation_enabled=True,
            meta_access_token=SecretStr("test-access-token"),
            meta_phone_number_id="",
        )
