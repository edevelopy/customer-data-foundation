"""Genera secretos efimeros solo para simulacros locales de release."""

from __future__ import annotations

import argparse
import json
import os
import secrets
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import quote

import jwt

SECRET_FILES = (
    "postgres_password",
    "database_url",
    "jwt_secret",
    "identifier_hash_key",
    "metrics_token",
    "partner_webhook_secret",
    "operator_token",
)


def write_private(path: Path, value: str) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as secret_file:
        secret_file.write(value)


def prepare_fixture(destination: Path, *, issuer: str, audience: str) -> list[str]:
    destination.mkdir(mode=0o700, parents=True, exist_ok=True)
    if any(destination.iterdir()):
        raise FileExistsError("release secret directory must be empty")

    postgres_password = secrets.token_urlsafe(48)
    jwt_secret = secrets.token_urlsafe(48)
    identifier_hash_key = secrets.token_urlsafe(48)
    partner_webhook_secret = secrets.token_urlsafe(48)
    metrics_token = secrets.token_urlsafe(48)
    database_url = (
        f"postgresql://fde_release:{quote(postgres_password, safe='')}@database:5432/fde_release"
    )
    now = datetime.now(UTC)
    operator_token = jwt.encode(
        {
            "sub": "release-smoke",
            "roles": ["operator"],
            "iss": issuer,
            "aud": audience,
            "iat": now,
            "exp": now + timedelta(hours=1),
        },
        jwt_secret,
        algorithm="HS256",
    )
    values = {
        "postgres_password": postgres_password,
        "database_url": database_url,
        "jwt_secret": jwt_secret,
        "identifier_hash_key": identifier_hash_key,
        "metrics_token": metrics_token,
        "partner_webhook_secret": partner_webhook_secret,
        "operator_token": operator_token,
    }
    for name, value in values.items():
        write_private(destination / name, value)
    return sorted(values)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--issuer", default="fde-release")
    parser.add_argument("--audience", default="fde-release-clients")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        files = prepare_fixture(args.destination, issuer=args.issuer, audience=args.audience)
    except (FileExistsError, OSError) as error:
        raise SystemExit("Disposable release secrets could not be prepared.") from error
    print(json.dumps({"files": files, "status": "prepared"}, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
