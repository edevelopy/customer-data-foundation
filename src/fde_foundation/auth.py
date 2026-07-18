"""Autenticacion Bearer JWT y autorizacion por roles del piloto."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt.exceptions import InvalidTokenError

from fde_foundation.settings import ConfigurationError, Settings

ALLOWED_ROLES = frozenset({"operator", "auditor"})
bearer_scheme = HTTPBearer(auto_error=False, scheme_name="BearerAuth")


@dataclass(frozen=True)
class Principal:
    subject: str
    roles: frozenset[str]


def api_settings() -> Settings:
    try:
        return Settings.from_environment()
    except ConfigurationError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "service_not_configured", "message": "Service is not ready."},
        ) from error


def unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"code": "invalid_token", "message": "Authentication is required."},
        headers={"WWW-Authenticate": "Bearer"},
    )


def authenticate(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Security(bearer_scheme)],
    settings: Annotated[Settings, Depends(api_settings)],
) -> Principal:
    if credentials is None or credentials.scheme.casefold() != "bearer":
        raise unauthorized()
    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.jwt_secret,
            algorithms=["HS256"],
            audience=settings.jwt_audience,
            issuer=settings.jwt_issuer,
            options={"require": ["exp", "sub", "iss", "aud", "roles"]},
        )
    except InvalidTokenError as error:
        raise unauthorized() from error

    subject = payload.get("sub")
    raw_roles = payload.get("roles")
    if not isinstance(subject, str) or not subject:
        raise unauthorized()
    if not isinstance(raw_roles, list) or not all(isinstance(role, str) for role in raw_roles):
        raise unauthorized()
    roles = frozenset(raw_roles) & ALLOWED_ROLES
    if not roles:
        raise unauthorized()
    return Principal(subject=subject, roles=roles)


def require_role(role: str) -> Callable[..., Principal]:
    def dependency(principal: Annotated[Principal, Depends(authenticate)]) -> Principal:
        if role not in principal.roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": "forbidden", "message": "Permission denied."},
            )
        return principal

    return dependency


require_operator = require_role("operator")
require_auditor = require_role("auditor")
