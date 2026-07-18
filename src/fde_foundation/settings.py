"""Configuracion explicita de la API sin imprimir valores sensibles."""

from __future__ import annotations

import os
from dataclasses import dataclass


class ConfigurationError(Exception):
    """La configuracion requerida no esta disponible o no es segura."""


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

    @classmethod
    def from_environment(cls) -> Settings:
        app_env = os.environ.get("APP_ENV", "production")
        database_url = os.environ.get("DATABASE_URL", "")
        jwt_secret = os.environ.get("JWT_SECRET", "")
        identifier_hash_key = os.environ.get("IDENTIFIER_HASH_KEY", "")
        jwt_issuer = os.environ.get("JWT_ISSUER", "")
        jwt_audience = os.environ.get("JWT_AUDIENCE", "")
        api_host = os.environ.get("API_HOST", "127.0.0.1")
        try:
            api_port = int(os.environ.get("API_PORT", "8000"))
        except ValueError as error:
            raise ConfigurationError from error

        if not database_url or not jwt_issuer or not jwt_audience:
            raise ConfigurationError
        if len(jwt_secret) < 32:
            raise ConfigurationError
        if len(identifier_hash_key) < 32:
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
        )
