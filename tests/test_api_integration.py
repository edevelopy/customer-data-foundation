from __future__ import annotations

import hashlib
import os
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

import jwt
import psycopg
import pytest
from fastapi.testclient import TestClient

from fde_foundation.api import app
from fde_foundation.api_store import complete_operation, protected_hash, reserve_operation
from fde_foundation.database import upgrade_database
from fde_foundation.importer import ImportResult, import_csv
from fde_foundation.validation import MAX_FILE_BYTES

DATABASE_URL = "postgresql://fde_test:test-only-password@localhost:55434/fde_test"
JWT_SECRET = "test-jwt-signing-key-with-more-than-thirty-two-characters"
IDENTIFIER_HASH_KEY = "test-identifier-hash-key-with-more-than-thirty-two-characters"
METRICS_TOKEN = "test-metrics-token-with-more-than-thirty-two-characters"
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
            "TRUNCATE TABLE partner_receipts, partner_delivery_attempts, integration_outbox, "
            "api_operations, customers, import_batches RESTART IDENTITY CASCADE;"
        )
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("JWT_SECRET", JWT_SECRET)
    monkeypatch.setenv("IDENTIFIER_HASH_KEY", IDENTIFIER_HASH_KEY)
    monkeypatch.setenv("METRICS_TOKEN", METRICS_TOKEN)
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


def reserve_abandoned_operation(
    *, database_url: str, subject: str, idempotency_key: str, content: bytes = VALID_CSV
):
    return reserve_operation(
        database_url=database_url,
        identifier_hash_key=IDENTIFIER_HASH_KEY,
        subject=subject,
        idempotency_key=idempotency_key,
        request_sha256=hashlib.sha256(content).hexdigest(),
    )


def expire_lease(database_url: str, operation_id) -> None:
    with psycopg.connect(database_url) as connection:
        connection.execute(
            "UPDATE api_operations SET lease_expires_at = now() - interval '1 second' "
            "WHERE operation_id = %s;",
            (operation_id,),
        )


@pytest.mark.integration
def test_health_endpoints_distinguish_live_and_ready(api_client: TestClient) -> None:
    assert api_client.get("/health/live").json() == {"status": "ok"}
    assert api_client.get("/health/ready").json() == {"status": "ready"}


@pytest.mark.integration
def test_metrics_require_dedicated_token_and_expose_no_customer_data(
    api_client: TestClient,
) -> None:
    assert api_client.get("/metrics").status_code == 401
    response = api_client.get("/metrics", headers={"Authorization": f"Bearer {METRICS_TOKEN}"})

    assert response.status_code == 200
    assert "fde_imports_total" in response.text
    assert "fde_outbox_dead_letter" in response.text
    assert "example.com" not in response.text


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

    owner_integration = api_client.get(
        f"/v1/integrations/{operation_id}", headers=headers("operator-1", ["operator"])
    )
    other_integration = api_client.get(
        f"/v1/integrations/{operation_id}", headers=headers("operator-2", ["operator"])
    )
    auditor_integration = api_client.get(
        f"/v1/integrations/{operation_id}", headers=headers("auditor-1", ["auditor"])
    )
    assert owner_integration.status_code == 200
    assert owner_integration.json()["status"] == "pending"
    assert owner_integration.json()["attempt_count"] == 0
    assert other_integration.status_code == 404
    assert auditor_integration.status_code == 200


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
        stored_hashes = connection.execute(
            "SELECT actor_hash, idempotency_key_hash FROM api_operations;"
        ).fetchone()
        event_count = connection.execute("SELECT count(*) FROM integration_outbox;").fetchone()
    assert stored_hashes is not None
    actor_hash, key_hash = stored_hashes

    assert actor_hash == protected_hash(IDENTIFIER_HASH_KEY, "actor", "operator-1")
    assert key_hash == protected_hash(IDENTIFIER_HASH_KEY, "idempotency", "import-key-0002")
    assert "operator-1" not in actor_hash
    assert "import-key-0002" not in key_hash
    assert event_count == (1,)


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


@pytest.mark.integration
def test_active_lease_returns_processing_with_retry_guidance(api_client: TestClient) -> None:
    database_url = os.environ.get("TEST_DATABASE_URL", DATABASE_URL)
    reservation = reserve_abandoned_operation(
        database_url=database_url,
        subject="operator-active",
        idempotency_key="import-key-active",
    )

    response = upload(
        api_client,
        headers("operator-active", ["operator"], "import-key-active"),
    )

    assert response.status_code == 202
    assert response.json()["status"] == "processing"
    assert response.json()["operation_id"] == str(reservation.operation.operation_id)
    assert response.json()["attempt_count"] == 1
    assert 1 <= int(response.headers["Retry-After"]) <= 6 * 60


@pytest.mark.integration
def test_expired_lease_recovers_same_operation(api_client: TestClient) -> None:
    database_url = os.environ.get("TEST_DATABASE_URL", DATABASE_URL)
    reservation = reserve_abandoned_operation(
        database_url=database_url,
        subject="operator-recovery",
        idempotency_key="import-key-recovery",
    )
    expire_lease(database_url, reservation.operation.operation_id)

    response = upload(
        api_client,
        headers("operator-recovery", ["operator"], "import-key-recovery"),
    )

    assert response.status_code == 200
    assert response.json()["status"] == "imported"
    assert response.json()["operation_id"] == str(reservation.operation.operation_id)
    assert response.json()["attempt_count"] == 2
    with psycopg.connect(database_url) as connection:
        operation = connection.execute(
            "SELECT attempt_count, recovered_at IS NOT NULL FROM api_operations;"
        ).fetchone()
        customer_count = connection.execute("SELECT count(*) FROM customers;").fetchone()
    assert operation == (2, True)
    assert customer_count == (1,)


@pytest.mark.integration
def test_recovery_after_data_commit_does_not_duplicate(api_client: TestClient, tmp_path) -> None:
    database_url = os.environ.get("TEST_DATABASE_URL", DATABASE_URL)
    csv_path = tmp_path / "committed-before-crash.csv"
    csv_path.write_bytes(VALID_CSV)
    reservation = reserve_abandoned_operation(
        database_url=database_url,
        subject="operator-after-commit",
        idempotency_key="import-key-after-commit",
    )
    committed_result = import_csv(csv_path, database_url)
    assert committed_result.status == "imported"
    expire_lease(database_url, reservation.operation.operation_id)

    response = upload(
        api_client,
        headers("operator-after-commit", ["operator"], "import-key-after-commit"),
    )

    assert response.status_code == 200
    assert response.json()["status"] == "already_imported"
    assert response.json()["operation_id"] == str(reservation.operation.operation_id)
    assert response.json()["attempt_count"] == 2
    with psycopg.connect(database_url) as connection:
        customer_count = connection.execute("SELECT count(*) FROM customers;").fetchone()
        batch_count = connection.execute("SELECT count(*) FROM import_batches;").fetchone()
    assert customer_count == (1,)
    assert batch_count == (1,)


@pytest.mark.integration
def test_one_concurrent_recovery_wins_and_stale_completion_is_fenced(
    api_client: TestClient,
) -> None:
    database_url = os.environ.get("TEST_DATABASE_URL", DATABASE_URL)
    initial = reserve_abandoned_operation(
        database_url=database_url,
        subject="operator-fenced",
        idempotency_key="import-key-fenced",
    )
    expire_lease(database_url, initial.operation.operation_id)

    def recover():
        return reserve_abandoned_operation(
            database_url=database_url,
            subject="operator-fenced",
            idempotency_key="import-key-fenced",
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        recoveries = list(executor.map(lambda _index: recover(), range(2)))

    assert sorted(reservation.recovered for reservation in recoveries) == [False, True]
    assert {reservation.operation.attempt_count for reservation in recoveries} == {2}
    result = ImportResult(True, "imported", 1, 1, 0, [])

    stale_completion = complete_operation(
        database_url,
        initial.operation.operation_id,
        1,
        result,
        10,
    )
    assert stale_completion.status == "processing"
    assert stale_completion.attempt_count == 2

    current_completion = complete_operation(
        database_url,
        initial.operation.operation_id,
        2,
        result,
        10,
    )
    assert current_completion.status == "imported"
    assert current_completion.attempt_count == 2
    with psycopg.connect(database_url) as connection:
        event_count = connection.execute("SELECT count(*) FROM integration_outbox;").fetchone()
    assert event_count == (1,)
