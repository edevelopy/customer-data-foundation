"""Configuracion explicita de la API sin imprimir valores sensibles."""

from __future__ import annotations

import os
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path

MAX_SECRET_BYTES = 8 * 1024


class ConfigurationError(Exception):
    """La configuracion requerida no esta disponible o no es segura."""


def read_optional_decimal(name: str) -> Decimal | None:
    raw_value = os.environ.get(name, "").strip()
    if not raw_value:
        return None
    try:
        value = Decimal(raw_value)
    except InvalidOperation as error:
        raise ConfigurationError from error
    if not value.is_finite() or value < 0:
        raise ConfigurationError
    return value


def has_config_source(name: str) -> bool:
    return name in os.environ or f"{name}_FILE" in os.environ


def read_secret(name: str, *, minimum_length: int = 32) -> str:
    """Lee un secreto directo o desde NAME_FILE sin revelar valores ni rutas en errores."""
    direct_value = os.environ.get(name)
    file_name = os.environ.get(f"{name}_FILE")
    if direct_value is not None and file_name is not None:
        raise ConfigurationError

    if file_name is not None:
        try:
            raw_value = Path(file_name).read_bytes()
            if len(raw_value) > MAX_SECRET_BYTES:
                raise ConfigurationError
            value = raw_value.decode("utf-8").rstrip("\r\n")
        except (OSError, UnicodeDecodeError) as error:
            raise ConfigurationError from error
    else:
        value = direct_value or ""

    if len(value) < minimum_length or "\n" in value or "\r" in value:
        raise ConfigurationError
    return value


@dataclass(frozen=True)
class Settings:
    app_env: str
    database_url: str
    jwt_secret: str
    identifier_hash_key: str
    jwt_issuer: str
    jwt_audience: str
    api_host: str
    api_port: int
    metrics_token: str = ""

    @classmethod
    def from_environment(cls) -> Settings:
        app_env = os.environ.get("APP_ENV", "production")
        database_url = read_secret("DATABASE_URL", minimum_length=1)
        jwt_secret = read_secret("JWT_SECRET")
        identifier_hash_key = read_secret("IDENTIFIER_HASH_KEY")
        metrics_token = read_secret("METRICS_TOKEN")
        jwt_issuer = os.environ.get("JWT_ISSUER", "")
        jwt_audience = os.environ.get("JWT_AUDIENCE", "")
        api_host = os.environ.get("API_HOST", "127.0.0.1")
        try:
            api_port = int(os.environ.get("API_PORT", "8000"))
        except ValueError as error:
            raise ConfigurationError from error

        if not database_url or not jwt_issuer or not jwt_audience:
            raise ConfigurationError
        if not 1 <= api_port <= 65535:
            raise ConfigurationError
        return cls(
            app_env=app_env,
            database_url=database_url,
            jwt_secret=jwt_secret,
            identifier_hash_key=identifier_hash_key,
            jwt_issuer=jwt_issuer,
            jwt_audience=jwt_audience,
            api_host=api_host,
            api_port=api_port,
            metrics_token=metrics_token,
        )


@dataclass(frozen=True)
class AISettings:
    api_key: str
    model: str
    timeout_seconds: float
    max_retries: int
    max_output_tokens: int
    input_cost_per_million_usd: Decimal | None
    output_cost_per_million_usd: Decimal | None

    @classmethod
    def from_environment(cls) -> AISettings:
        api_key = read_secret("OPENAI_API_KEY", minimum_length=20)
        model = os.environ.get("OPENAI_MODEL", "gpt-5.6-sol").strip()
        try:
            timeout_seconds = float(os.environ.get("OPENAI_TIMEOUT_SECONDS", "30"))
            max_retries = int(os.environ.get("OPENAI_MAX_RETRIES", "2"))
            max_output_tokens = int(os.environ.get("OPENAI_MAX_OUTPUT_TOKENS", "500"))
        except ValueError as error:
            raise ConfigurationError from error

        if not model or any(character.isspace() for character in model):
            raise ConfigurationError
        if not 1 <= timeout_seconds <= 120:
            raise ConfigurationError
        if not 0 <= max_retries <= 5:
            raise ConfigurationError
        if not 64 <= max_output_tokens <= 4096:
            raise ConfigurationError

        return cls(
            api_key=api_key,
            model=model,
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
            max_output_tokens=max_output_tokens,
            input_cost_per_million_usd=read_optional_decimal("OPENAI_INPUT_COST_PER_MILLION_USD"),
            output_cost_per_million_usd=read_optional_decimal("OPENAI_OUTPUT_COST_PER_MILLION_USD"),
        )
