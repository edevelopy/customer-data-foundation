from __future__ import annotations

import jwt
import pytest

from fde_foundation.dev_token import build_token
from fde_foundation.settings import Settings


def settings(app_env: str = "development") -> Settings:
    return Settings(
        app_env=app_env,
        database_url="postgresql://unused",
        jwt_secret="test-jwt-signing-key-with-more-than-thirty-two-characters",
        identifier_hash_key="test-identifier-hash-key-with-more-than-thirty-two-characters",
        jwt_issuer="fde-test",
        jwt_audience="fde-audience",
        api_host="127.0.0.1",
        api_port=8000,
    )


def test_development_token_has_fixed_claims_and_short_lifetime() -> None:
    encoded = build_token(settings(), "operator-demo", "operator")

    payload = jwt.decode(
        encoded,
        settings().jwt_secret,
        algorithms=["HS256"],
        issuer="fde-test",
        audience="fde-audience",
    )

    assert payload["sub"] == "operator-demo"
    assert payload["roles"] == ["operator"]
    assert payload["exp"] - payload["iat"] == 15 * 60


@pytest.mark.parametrize(
    ("app_env", "subject", "role"),
    [
        ("production", "operator-demo", "operator"),
        ("development", "name@example.com", "operator"),
        ("development", "operator-demo", "administrator"),
    ],
)
def test_development_token_rejects_unsafe_contexts(app_env: str, subject: str, role: str) -> None:
    with pytest.raises(ValueError):
        build_token(settings(app_env), subject, role)
