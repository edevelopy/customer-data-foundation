"""Outbox durable para entregar eventos sin acoplar la importacion a la API socia."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Final

import psycopg
from psycopg.types.json import Jsonb

from fde_foundation.database import (
    CONNECT_TIMEOUT_SECONDS,
    POSTGRES_OPERATION_LIMITS,
    require_current_schema,
)

EVENT_TYPE: Final = "customer_import.completed"
EVENT_SCHEMA_VERSION: Final = "1.0"
OUTBOX_COLUMNS: Final = """
event_id, operation_id, event_type, payload, status, attempt_count,
available_at, lease_expires_at, last_failure_code, delivered_at
"""


@dataclass(frozen=True)
class OutboxEvent:
    event_id: uuid.UUID
    operation_id: uuid.UUID
    event_type: str
    payload: dict[str, object]
    status: str
    attempt_count: int
    available_at: datetime
    lease_expires_at: datetime | None
    last_failure_code: str | None
    delivered_at: datetime | None


def connect(database_url: str, *, application_name: str = "fde-integration") -> psycopg.Connection:
    return psycopg.connect(
        database_url,
        connect_timeout=CONNECT_TIMEOUT_SECONDS,
        options=POSTGRES_OPERATION_LIMITS,
        application_name=application_name,
    )


def event_from_row(row: tuple[object, ...]) -> OutboxEvent:
    return OutboxEvent(
        event_id=row[0],
        operation_id=row[1],
        event_type=row[2],
        payload=dict(row[3]),
        status=row[4],
        attempt_count=row[5],
        available_at=row[6],
        lease_expires_at=row[7],
        last_failure_code=row[8],
        delivered_at=row[9],
    )


def enqueue_completed_import(
    connection: psycopg.Connection,
    *,
    operation_id: uuid.UUID,
    import_status: str,
    total_rows: int,
    inserted_rows: int,
    existing_rows: int,
) -> uuid.UUID:
    """Inserta una sola notificacion tecnica dentro de la transaccion del resultado."""
    event_id = uuid.uuid4()
    payload: dict[str, object] = {
        "event_id": str(event_id),
        "event_type": EVENT_TYPE,
        "existing_rows": existing_rows,
        "inserted_rows": inserted_rows,
        "occurred_at": datetime.now(UTC).isoformat(),
        "operation_id": str(operation_id),
        "schema_version": EVENT_SCHEMA_VERSION,
        "status": import_status,
        "total_rows": total_rows,
    }
    row = connection.execute(
        """
        INSERT INTO integration_outbox (
            event_id, operation_id, event_type, payload
        ) VALUES (%s, %s, %s, %s)
        ON CONFLICT (operation_id) DO UPDATE
            SET operation_id = EXCLUDED.operation_id
        RETURNING event_id;
        """,
        (event_id, operation_id, EVENT_TYPE, Jsonb(payload)),
    ).fetchone()
    if row is None:
        raise psycopg.DatabaseError
    return row[0]


def claim_next_event(database_url: str, *, lease_seconds: int) -> OutboxEvent | None:
    """Reserva atomicamente un evento disponible; varios workers pueden competir sin duplicarlo."""
    with (
        connect(database_url, application_name="fde-integration-worker") as connection,
        connection.transaction(),
    ):
        require_current_schema(connection)
        row = connection.execute(
            """
                WITH candidate AS (
                    SELECT event_id
                    FROM integration_outbox
                    WHERE available_at <= now()
                      AND (
                        status = 'pending'
                        OR (
                            status = 'delivering'
                            AND lease_expires_at <= now()
                        )
                      )
                    ORDER BY available_at, created_at
                    FOR UPDATE SKIP LOCKED
                    LIMIT 1
                )
                UPDATE integration_outbox AS event
                SET status = 'delivering',
                    attempt_count = event.attempt_count + 1,
                    lease_expires_at = now() + (%s * interval '1 second'),
                    updated_at = now()
                FROM candidate
                WHERE event.event_id = candidate.event_id
                RETURNING
                    event.event_id,
                    event.operation_id,
                    event.event_type,
                    event.payload,
                    event.status,
                    event.attempt_count,
                    event.available_at,
                    event.lease_expires_at,
                    event.last_failure_code,
                    event.delivered_at;
                """,
            (lease_seconds,),
        ).fetchone()
    return event_from_row(row) if row is not None else None


def mark_delivered(database_url: str, event: OutboxEvent) -> bool:
    """Finaliza solo el intento que conserva el fencing token attempt_count."""
    with (
        connect(database_url, application_name="fde-integration-worker") as connection,
        connection.transaction(),
    ):
        require_current_schema(connection)
        row = connection.execute(
            """
                UPDATE integration_outbox
                SET status = 'delivered',
                    lease_expires_at = NULL,
                    delivered_at = now(),
                    updated_at = now()
                WHERE event_id = %s
                  AND status = 'delivering'
                  AND attempt_count = %s
                RETURNING event_id;
                """,
            (event.event_id, event.attempt_count),
        ).fetchone()
    return row is not None


def mark_failed_attempt(
    database_url: str,
    event: OutboxEvent,
    *,
    error_code: str,
    retryable: bool,
    max_attempts: int,
    base_backoff_seconds: int,
    max_backoff_seconds: int,
) -> str:
    """Programa backoff exponencial o envia el evento a dead letter."""
    exhausted = event.attempt_count >= max_attempts
    next_status = "pending" if retryable and not exhausted else "dead_letter"
    backoff_seconds = min(
        max_backoff_seconds,
        base_backoff_seconds * (2 ** max(0, event.attempt_count - 1)),
    )
    with (
        connect(database_url, application_name="fde-integration-worker") as connection,
        connection.transaction(),
    ):
        require_current_schema(connection)
        row = connection.execute(
            """
                UPDATE integration_outbox
                SET status = %s,
                    available_at = CASE
                        WHEN %s = 'pending' THEN now() + (%s * interval '1 second')
                        ELSE available_at
                    END,
                    lease_expires_at = NULL,
                    last_failure_code = %s,
                    updated_at = now()
                WHERE event_id = %s
                  AND status = 'delivering'
                  AND attempt_count = %s
                RETURNING status;
                """,
            (
                next_status,
                next_status,
                backoff_seconds,
                error_code,
                event.event_id,
                event.attempt_count,
            ),
        ).fetchone()
    if row is None:
        return "stale_attempt"
    return row[0]


def get_event_for_operation(database_url: str, operation_id: uuid.UUID) -> OutboxEvent | None:
    with (
        connect(database_url, application_name="fde-api") as connection,
        connection.transaction(),
    ):
        require_current_schema(connection)
        row = connection.execute(
            f"SELECT {OUTBOX_COLUMNS} FROM integration_outbox WHERE operation_id = %s;",
            (operation_id,),
        ).fetchone()
    return event_from_row(row) if row is not None else None
