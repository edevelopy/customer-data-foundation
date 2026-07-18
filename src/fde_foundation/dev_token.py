"""Genera una credencial JWT de corta duracion solo para desarrollo local."""

from __future__ import annotations

import argparse
import re
from datetime import UTC, datetime, timedelta

import jwt

from fde_foundation.settings import ConfigurationError, Settings

SUBJECT_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,64}$")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--subject", required=True, help="identificador tecnico sin PII")
    parser.add_argument("--role", required=True, choices=("operator", "auditor"))
    return parser.parse_args()


def build_token(settings: Settings, subject: str, role: str) -> str:
    if settings.app_env != "development":
        raise ValueError("development environment required")
    if not SUBJECT_PATTERN.fullmatch(subject):
        raise ValueError("invalid subject")
    if role not in {"operator", "auditor"}:
        raise ValueError("invalid role")
    now = datetime.now(UTC)
    return jwt.encode(
        {
            "sub": subject,
            "roles": [role],
            "iss": settings.jwt_issuer,
            "aud": settings.jwt_audience,
            "iat": now,
            "exp": now + timedelta(minutes=15),
        },
        settings.jwt_secret,
        algorithm="HS256",
    )


def main() -> int:
    args = parse_args()
    try:
        settings = Settings.from_environment()
        encoded_token = build_token(settings, args.subject, args.role)
    except (ConfigurationError, ValueError) as error:
        raise SystemExit("Development token generation is not available.") from error
    print(encoded_token)
    return 0
