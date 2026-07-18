from __future__ import annotations

import os
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

import jwt
import psycopg
import pytest
from fastapi.testclient import TestClient

from fde_foundation.api import app
from fde_foundation.api_store import protected_hash, reserve_operation
from fde_foundation.database import upgrade_database
from fde_foundation.validation import MAX_FILE_BYTES

DATABASE_URL = "postgresql://fde_test:test-only-password@localhost:55434/fde_test"
JWT_SECRET = "test-jwt-signing-key-with-more-than-thirty-two-characters"
IDENTIFIER_HASH_KEY = "test-identifier-hash-key-with-more-than-thirty-two-characters"
JWT_ISSUER = "fde-test"
JWT_AUDIENCE = "fde-import-api-test"
VALID_CSV = (
    b"email,first_name,last_name,phone,source\n"
    b"alice@example.com,Alice,Rivera,+14075550101,partner\n"
)


@pytest.fixture
def api_client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    database_url = os.environ.get("TEST_DATABASE_URL", DATABASE_URL)
    upgrade_database(database_url)
    with psycopg.connect(database_url) as connection:
        connection.execute(
            "TRUNCATE TABLE api_operations, customers, import_batches RESTART IDENTITY CASCADE;"
        )
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("JWT_SECRET", JWT_SECRET)
    monkeypatch.setenv("IDENTIFIER_HASH_KEY", IDENTIFIER_HASH_KEY)
    monkeypatch.setenv("JWT_ISSUER", JWT_ISSUER)
    monkeypatch.setenv("JWT_AUDIENCE", JWT_AUDIENCE)
    with TestClient(app) as client:
        yield client


def token(subject: str, roles: list[str]) -> str:
    now = datetime.now(UTC)
    return jwt.encode(
        {
            "sub": subject,
            "roles": roles,
            "iss": JWT_ISSUER,
            "aud": JWT_AUDIENCE,
            "iat": now,
            "exp": now + timedelta(minutes=5),
        },
        JWT_SECRET,
        algorithm="HS256",
    )


def headers(subject: str, roles: list[str], idempotency_key: str | None = None) -> dict[str, str]:
    result = {"Authorization": f"Bearer {token(subject, roles)}"}
    if idempotency_key:
        result["Idempotency-Key"] = idempotency_key
    return result


def upload(client: TestClient, request_headers: dict[str, str], content: bytes = VALID_CSV):
    return client.post(
        "/v1/imports",
        headers=request_headers,
        files={"file": ("customers.csv", content, "text/csv")},
    )


@pytest.mark.integration
def test_health_endpoints_distinguish_live_and_ready(api_client: TestClient) -> None:
    assert api_client.get("/health/live").json() == {"status": "ok"}
    assert api_client.get("/health/ready").json() == {"status": "ready"}


@pytest.mark.integration
def test_operator_imports_and_access_is_scoped(api_client: TestClient) -> None:
    response = upload(api_client, headers("operator-1", ["operator"], "import-key-0001"))

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "imported"
    assert payload["inserted_rows"] == 1
    assert "alice@example.com" not in response.text
    operation_id = payload["operation_id"]

    owner = api_client.get(
        f"/v1/imports/{operation_id}", headers=headers("operator-1", ["operator"])
    )
    other_operator = api_client.get(
        f"/v1/imports/{operation_id}", headers=headers("operator-2", ["operator"])
    )
    auditor = api_client.get(
        f"/v1/imports/{operation_id}", headers=headers("auditor-1", ["auditor"])
    )

    assert owner.status_code == 200
    assert other_operator.status_code == 404
    assert auditor.status_code == 200


@pytest.mark.integration
def test_exact_idempotent_replay_returns_same_operation(api_client: TestClient) -> None:
    request_headers = headers("operator-1", ["operator"], "import-key-0002")

    first = upload(api_client, request_headers)
    second = upload(api_client, request_headers)

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json() == second.json()

    database_url = os.environ.get("TEST_DATABASE_URL", DATABASE_URL)
    with psycopg.connect(database_url) as connection:
        actor_hash, key_hash = connection.execute(
            "SELECT actor_hash, idempotency_key_hash FROM api_operations;"
        ).fetchone()

    assert actor_hash == protected_hash(IDENTIFIER_HASH_KEY, "actor", "operator-1")
    assert key_hash == protected_hash(IDENTIFIER_HASH_KEY, "idempotency", "import-key-0002")
    assert "operator-1" not in actor_hash
    assert "import-key-0002" not in key_hash


@pytest.mark.integration
def test_reusing_key_for_different_file_is_rejected(api_client: TestClient) -> None:
    request_headers = headers("operator-1", ["operator"], "import-key-0003")
    different_csv = (
        b"email,first_name,last_name,phone,source\n"
        b"bob@example.com,Bob,Smith,+14075550102,internal\n"
    )

    assert upload(api_client, request_headers).status_code == 200
    response = upload(api_client, request_headers, different_csv)

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "idempotency_key_reused"
    assert "bob@example.com" not in response.text


@pytest.mark.integration
def test_auditor_cannot_submit_and_authentication_is_required(api_client: TestClient) -> None:
    auditor = upload(api_client, headers("auditor-1", ["auditor"], "import-key-0004"))
    anonymous = api_client.post(
        "/v1/imports",
        headers={"Idempotency-Key": "import-key-0005"},
        files={"file": ("customers.csv", VALID_CSV, "text/csv")},
    )

    assert auditor.status_code == 403
    assert anonymous.status_code == 401


@pytest.mark.integration
def test_expired_and_wrong_audience_tokens_are_rejected(api_client: TestClient) -> None:
    now = datetime.now(UTC)

    def encoded(expiration: datetime, audience: str) -> str:
        return jwt.encode(
            {
                "sub": "operator-1",
                "roles": ["operator"],
                "iss": JWT_ISSUER,
                "aud": audience,
                "iat": now - timedelta(minutes=10),
                "exp": expiration,
            },
            JWT_SECRET,
            algorithm="HS256",
        )

    expired = encoded(now - timedelta(minutes=5), JWT_AUDIENCE)
    wrong_audience = encoded(now + timedelta(minutes=5), "another-service")

    for invalid_token in (expired, wrong_audience):
        response = upload(
            api_client,
            {
                "Authorization": f"Bearer {invalid_token}",
                "Idempotency-Key": "import-key-unauthorized",
            },
        )
        assert response.status_code == 401
        assert response.json()["detail"]["code"] == "invalid_token"
        assert invalid_token not in response.text


@pytest.mark.integration
def test_invalid_csv_returns_safe_actionable_errors(api_client: TestClient) -> None:
    invalid_csv = (
        b"email,first_name,last_name,phone,source\n"
        b"private.person@example.com,,Rivera,4075550101,partner\n"
    )

    response = upload(
        api_client,
        headers("operator-1", ["operator"], "import-key-0006"),
        invalid_csv,
    )

    assert response.status_code == 422
    assert response.json()["status"] == "validation_failed"
    assert response.json()["error_codes"] == ["invalid_format", "required"]
    assert "private.person@example.com" not in response.text
    assert "4075550101" not in response.text


@pytest.mark.integration
def test_missing_key_and_oversized_file_are_rejected(api_client: TestClient) -> None:
    missing_key = upload(api_client, headers("operator-1", ["operator"]))
    oversized = upload(
        api_client,
        headers("operator-1", ["operator"], "import-key-0007"),
        b"x" * (MAX_FILE_BYTES + 1),
    )

    assert missing_key.status_code == 400
    assert missing_key.json()["detail"]["code"] == "invalid_idempotency_key"
    assert oversized.status_code == 413
    assert oversized.json()["detail"]["code"] == "file_too_large"


@pytest.mark.integration
def test_concurrent_reservations_share_one_operation(api_client: TestClient) -> None:
    database_url = os.environ.get("TEST_DATABASE_URL", DATABASE_URL)

    def reserve():
        return reserve_operation(
            database_url=database_url,
            identifier_hash_key=IDENTIFIER_HASH_KEY,
            subject="operator-concurrent",
            idempotency_key="import-key-concurrent",
            request_sha256="a" * 64,
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        reservations = list(executor.map(lambda _index: reserve(), range(2)))

    assert sorted(reservation.created for reservation in reservations) == [False, True]
    assert len({reservation.operation.operation_id for reservation in reservations}) == 1
