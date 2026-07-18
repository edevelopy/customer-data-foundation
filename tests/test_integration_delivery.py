from __future__ import annotations

import os
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from urllib.error import HTTPError

import psycopg
import pytest
from fastapi.testclient import TestClient

import fde_foundation.integration_worker as worker_module
from fde_foundation.database import upgrade_database
from fde_foundation.integration_store import (
    EVENT_SCHEMA_VERSION,
    EVENT_TYPE,
    claim_next_event,
    enqueue_completed_import,
    get_event_for_operation,
    mark_delivered,
    mark_failed_attempt,
)
from fde_foundation.integration_worker import (
    WorkerSettings,
    canonical_body,
    deliver_event,
    signature,
)
from fde_foundation.partner_api import partner_app

DATABASE_URL = "postgresql://fde_test:test-only-password@localhost:55434/fde_test"
WEBHOOK_SECRET = "test-partner-webhook-secret-with-more-than-thirty-two-characters"


@pytest.fixture
def database_url(monkeypatch: pytest.MonkeyPatch) -> str:
    url = os.environ.get("TEST_DATABASE_URL", DATABASE_URL)
    upgrade_database(url)
    with psycopg.connect(url) as connection:
        connection.execute(
            "TRUNCATE TABLE partner_receipts, partner_delivery_attempts, integration_outbox, "
            "api_operations, customers, import_batches RESTART IDENTITY CASCADE;"
        )
    monkeypatch.setenv("PARTNER_DATABASE_URL", url)
    monkeypatch.setenv("PARTNER_WEBHOOK_SECRET", WEBHOOK_SECRET)
    monkeypatch.setenv("PARTNER_SIMULATED_FAILURES", "0")
    return url


def insert_outbox_event(database_url: str) -> uuid.UUID:
    operation_id = uuid.uuid4()
    with psycopg.connect(database_url) as connection, connection.transaction():
        connection.execute(
            """
            INSERT INTO api_operations (
                operation_id, actor_hash, idempotency_key_hash, request_sha256, status,
                accepted, total_rows, inserted_rows, existing_rows, lease_expires_at
            ) VALUES (%s, %s, %s, %s, 'imported', true, 3, 2, 1, now());
            """,
            (operation_id, "a" * 64, "b" * 64, "c" * 64),
        )
        enqueue_completed_import(
            connection,
            operation_id=operation_id,
            import_status="imported",
            total_rows=3,
            inserted_rows=2,
            existing_rows=1,
        )
    return operation_id


def worker_settings(database_url: str) -> WorkerSettings:
    return WorkerSettings(
        database_url=database_url,
        partner_url="http://partner.test/partner/v1/import-events",
        webhook_secret=WEBHOOK_SECRET,
        timeout_seconds=0.2,
        max_attempts=3,
        base_backoff_seconds=1,
        max_backoff_seconds=4,
        lease_seconds=5,
        poll_seconds=0.05,
    )


def sample_payload(event_id: uuid.UUID | None = None) -> dict[str, object]:
    chosen_event_id = event_id or uuid.uuid4()
    return {
        "event_id": str(chosen_event_id),
        "event_type": EVENT_TYPE,
        "existing_rows": 1,
        "inserted_rows": 2,
        "occurred_at": datetime.now(UTC).isoformat(),
        "operation_id": str(uuid.uuid4()),
        "schema_version": EVENT_SCHEMA_VERSION,
        "status": "imported",
        "total_rows": 3,
    }


def signed_headers(body: bytes, event_id: uuid.UUID, *, timestamp: str | None = None):
    timestamp_value = timestamp or str(int(time.time()))
    return {
        "Content-Type": "application/json",
        "Idempotency-Key": str(event_id),
        "X-FDE-Event-Id": str(event_id),
        "X-FDE-Signature": signature(WEBHOOK_SECRET, timestamp_value, body),
        "X-FDE-Timestamp": timestamp_value,
    }


@pytest.mark.integration
def test_partner_contract_verifies_signature_and_is_idempotent(database_url: str) -> None:
    event_id = uuid.uuid4()
    payload = sample_payload(event_id)
    body = canonical_body(payload)

    with TestClient(partner_app) as client:
        first = client.post(
            "/partner/v1/import-events", content=body, headers=signed_headers(body, event_id)
        )
        duplicate = client.post(
            "/partner/v1/import-events", content=body, headers=signed_headers(body, event_id)
        )
        invalid_signature = client.post(
            "/partner/v1/import-events",
            content=body,
            headers={**signed_headers(body, event_id), "X-FDE-Signature": "v1=invalid"},
        )
        extra_payload = {**payload, "email": "must-not-be-accepted@example.com"}
        extra_body = canonical_body(extra_payload)
        unexpected_field = client.post(
            "/partner/v1/import-events",
            content=extra_body,
            headers=signed_headers(extra_body, event_id),
        )

    assert first.status_code == 200
    assert first.json() == {"event_id": str(event_id), "accepted": True, "duplicate": False}
    assert duplicate.status_code == 200
    assert duplicate.json()["duplicate"] is True
    assert invalid_signature.status_code == 401
    assert invalid_signature.json()["detail"]["code"] == "invalid_signature"
    assert unexpected_field.status_code == 422
    assert unexpected_field.json()["detail"]["code"] == "invalid_event"
    assert set(payload) == {
        "event_id",
        "event_type",
        "existing_rows",
        "inserted_rows",
        "occurred_at",
        "operation_id",
        "schema_version",
        "status",
        "total_rows",
    }


@pytest.mark.integration
def test_partner_rejects_expired_and_conflicting_events(database_url: str) -> None:
    event_id = uuid.uuid4()
    payload = sample_payload(event_id)
    body = canonical_body(payload)
    expired_timestamp = str(int(time.time()) - 301)

    with TestClient(partner_app) as client:
        expired = client.post(
            "/partner/v1/import-events",
            content=body,
            headers=signed_headers(body, event_id, timestamp=expired_timestamp),
        )
        assert (
            client.post(
                "/partner/v1/import-events", content=body, headers=signed_headers(body, event_id)
            ).status_code
            == 200
        )
        changed_payload = {**payload, "inserted_rows": 1, "existing_rows": 2}
        changed_body = canonical_body(changed_payload)
        conflict = client.post(
            "/partner/v1/import-events",
            content=changed_body,
            headers=signed_headers(changed_body, event_id),
        )

    assert expired.status_code == 401
    assert expired.json()["detail"]["code"] == "expired_signature"
    assert conflict.status_code == 409
    assert conflict.json()["detail"]["code"] == "event_id_reused"


@pytest.mark.integration
def test_partner_transient_failure_then_accepts_same_event(
    database_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PARTNER_SIMULATED_FAILURES", "1")
    event_id = uuid.uuid4()
    body = canonical_body(sample_payload(event_id))

    with TestClient(partner_app) as client:
        first = client.post(
            "/partner/v1/import-events", content=body, headers=signed_headers(body, event_id)
        )
        second = client.post(
            "/partner/v1/import-events", content=body, headers=signed_headers(body, event_id)
        )

    assert first.status_code == 503
    assert first.headers["Retry-After"] == "1"
    assert second.status_code == 200
    with psycopg.connect(database_url) as connection:
        attempts = connection.execute(
            "SELECT attempt_count FROM partner_delivery_attempts WHERE event_id = %s;",
            (event_id,),
        ).fetchone()
        receipts = connection.execute("SELECT count(*) FROM partner_receipts;").fetchone()
    assert attempts == (2,)
    assert receipts == (1,)


@pytest.mark.integration
def test_outbox_claim_backoff_delivery_and_fencing(database_url: str) -> None:
    operation_id = insert_outbox_event(database_url)
    first = claim_next_event(database_url, lease_seconds=5)

    assert first is not None
    assert first.operation_id == operation_id
    assert first.status == "delivering"
    assert first.attempt_count == 1
    assert (
        mark_failed_attempt(
            database_url,
            first,
            error_code="partner_http_503",
            retryable=True,
            max_attempts=3,
            base_backoff_seconds=1,
            max_backoff_seconds=4,
        )
        == "pending"
    )
    assert claim_next_event(database_url, lease_seconds=5) is None

    with psycopg.connect(database_url) as connection:
        connection.execute(
            "UPDATE integration_outbox SET available_at = now() WHERE operation_id = %s;",
            (operation_id,),
        )
    second = claim_next_event(database_url, lease_seconds=5)
    assert second is not None
    assert second.attempt_count == 2
    assert mark_delivered(database_url, first) is False
    assert mark_delivered(database_url, second) is True

    final = get_event_for_operation(database_url, operation_id)
    assert final is not None
    assert final.status == "delivered"
    assert final.attempt_count == 2
    assert final.last_failure_code == "partner_http_503"


@pytest.mark.integration
def test_concurrent_workers_claim_event_once(database_url: str) -> None:
    insert_outbox_event(database_url)

    with ThreadPoolExecutor(max_workers=2) as executor:
        claimed = list(
            executor.map(lambda _: claim_next_event(database_url, lease_seconds=5), range(2))
        )

    assert sum(event is not None for event in claimed) == 1


@pytest.mark.integration
def test_retry_budget_exhaustion_moves_event_to_dead_letter(database_url: str) -> None:
    operation_id = insert_outbox_event(database_url)
    event = claim_next_event(database_url, lease_seconds=5)
    assert event is not None

    status = mark_failed_attempt(
        database_url,
        event,
        error_code="partner_http_503",
        retryable=True,
        max_attempts=1,
        base_backoff_seconds=1,
        max_backoff_seconds=4,
    )

    final = get_event_for_operation(database_url, operation_id)
    assert status == "dead_letter"
    assert final is not None
    assert final.status == "dead_letter"
    assert claim_next_event(database_url, lease_seconds=5) is None


def test_worker_signs_exact_body_and_classifies_timeout(
    database_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    operation_id = insert_outbox_event(database_url)
    event = claim_next_event(database_url, lease_seconds=5)
    assert event is not None
    captured: dict[str, object] = {}

    class Response:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    def success(request, timeout):
        captured["body"] = request.data
        captured["headers"] = {key.lower(): value for key, value in request.header_items()}
        captured["timeout"] = timeout
        return Response()

    monkeypatch.setattr(worker_module, "urlopen", success)
    delivered = deliver_event(event, worker_settings(database_url))

    assert delivered.delivered is True
    assert captured["body"] == canonical_body(event.payload)
    assert captured["headers"]["idempotency-key"] == str(event.event_id)
    assert captured["headers"]["x-fde-signature"].startswith("v1=")
    assert captured["timeout"] == 0.2
    assert event.operation_id == operation_id

    def timeout(_request, timeout):
        assert timeout == 0.2
        raise TimeoutError

    monkeypatch.setattr(worker_module, "urlopen", timeout)
    timed_out = deliver_event(event, worker_settings(database_url))
    assert timed_out.delivered is False
    assert timed_out.retryable is True
    assert timed_out.error_code == "partner_timeout"


def test_worker_does_not_retry_permanent_partner_rejection(
    database_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    insert_outbox_event(database_url)
    event = claim_next_event(database_url, lease_seconds=5)
    assert event is not None

    def unauthorized(request, timeout):
        assert timeout == 0.2
        raise HTTPError(request.full_url, 401, "unauthorized", {}, None)

    monkeypatch.setattr(worker_module, "urlopen", unauthorized)
    result = deliver_event(event, worker_settings(database_url))

    assert result.delivered is False
    assert result.retryable is False
    assert result.error_code == "partner_http_401"
