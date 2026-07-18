"""Persistencia segura de operaciones HTTP e idempotencia."""

from __future__ import annotations

import hashlib
import hmac
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime

import psycopg
from psycopg.types.json import Jsonb

from fde_foundation.database import (
    CONNECT_TIMEOUT_SECONDS,
    POSTGRES_OPERATION_LIMITS,
    RECOVERY_LEASE_SECONDS,
    require_current_schema,
)
from fde_foundation.importer import ImportResult
from fde_foundation.integration_store import enqueue_completed_import

SELECT_OPERATION_COLUMNS = """
operation_id, actor_hash, request_sha256, status, accepted, total_rows,
inserted_rows, existing_rows, duration_ms, error_codes, issues,
attempt_count, lease_expires_at
"""


@dataclass(frozen=True)
class StoredOperation:
    operation_id: uuid.UUID
    actor_hash: str
    request_sha256: str
    status: str
    accepted: bool
    total_rows: int
    inserted_rows: int
    existing_rows: int
    duration_ms: int
    error_codes: tuple[str, ...]
    issues: list[dict[str, object]]
    attempt_count: int
    lease_expires_at: datetime


@dataclass(frozen=True)
class Reservation:
    created: bool
    recovered: bool
    operation: StoredOperation

    @property
    def should_process(self) -> bool:
        return self.created or self.recovered


def protected_hash(secret: str, namespace: str, value: str) -> str:
    message = f"{namespace}:{value}".encode()
    return hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()


def connect(database_url: str) -> psycopg.Connection:
    return psycopg.connect(
        database_url,
        connect_timeout=CONNECT_TIMEOUT_SECONDS,
        options=POSTGRES_OPERATION_LIMITS,
        application_name="fde-api",
    )


def operation_from_row(row: tuple[object, ...]) -> StoredOperation:
    return StoredOperation(
        operation_id=row[0],
        actor_hash=row[1],
        request_sha256=row[2],
        status=row[3],
        accepted=row[4],
        total_rows=row[5],
        inserted_rows=row[6],
        existing_rows=row[7],
        duration_ms=row[8],
        error_codes=tuple(row[9]),
        issues=list(row[10]),
        attempt_count=row[11],
        lease_expires_at=row[12],
    )


def reserve_operation(
    *,
    database_url: str,
    identifier_hash_key: str,
    subject: str,
    idempotency_key: str,
    request_sha256: str,
) -> Reservation:
    actor_hash = protected_hash(identifier_hash_key, "actor", subject)
    key_hash = protected_hash(identifier_hash_key, "idempotency", idempotency_key)
    operation_id = uuid.uuid4()
    with connect(database_url) as connection, connection.transaction():
        require_current_schema(connection)
        inserted = connection.execute(
            """
            INSERT INTO api_operations (
                operation_id, actor_hash, idempotency_key_hash, request_sha256, status,
                lease_expires_at
            ) VALUES (
                %s, %s, %s, %s, 'processing',
                now() + (%s * interval '1 second')
            )
            ON CONFLICT (actor_hash, idempotency_key_hash) DO NOTHING
            RETURNING operation_id;
            """,
            (
                operation_id,
                actor_hash,
                key_hash,
                request_sha256,
                RECOVERY_LEASE_SECONDS,
            ),
        ).fetchone()
        recovered = None
        if inserted is None:
            recovered = connection.execute(
                f"""
                UPDATE api_operations
                SET lease_expires_at = now() + (%s * interval '1 second'),
                    attempt_count = attempt_count + 1,
                    recovered_at = now()
                WHERE actor_hash = %s
                  AND idempotency_key_hash = %s
                  AND request_sha256 = %s
                  AND status = 'processing'
                  AND lease_expires_at <= now()
                RETURNING {SELECT_OPERATION_COLUMNS};
                """,
                (
                    RECOVERY_LEASE_SECONDS,
                    actor_hash,
                    key_hash,
                    request_sha256,
                ),
            ).fetchone()
        row = recovered
        if row is None:
            row = connection.execute(
                f"SELECT {SELECT_OPERATION_COLUMNS} FROM api_operations "
                "WHERE actor_hash = %s AND idempotency_key_hash = %s;",
                (actor_hash, key_hash),
            ).fetchone()
    if row is None:
        raise psycopg.DatabaseError
    return Reservation(
        created=inserted is not None,
        recovered=recovered is not None,
        operation=operation_from_row(row),
    )


def complete_operation(
    database_url: str,
    operation_id: uuid.UUID,
    attempt_count: int,
    result: ImportResult,
    duration_ms: int,
) -> StoredOperation:
    error_codes = sorted({item.code for item in result.issues})
    issues = [asdict(item) for item in result.issues]
    with connect(database_url) as connection, connection.transaction():
        require_current_schema(connection)
        row = connection.execute(
            f"""
            UPDATE api_operations
            SET status = %s,
                accepted = %s,
                total_rows = %s,
                inserted_rows = %s,
                existing_rows = %s,
                duration_ms = %s,
                error_codes = %s,
                issues = %s,
                completed_at = now()
            WHERE operation_id = %s
              AND attempt_count = %s
              AND status = 'processing'
            RETURNING {SELECT_OPERATION_COLUMNS};
            """,
            (
                result.status,
                result.accepted,
                result.total_rows,
                result.inserted_rows,
                result.existing_rows,
                duration_ms,
                error_codes,
                Jsonb(issues),
                operation_id,
                attempt_count,
            ),
        ).fetchone()
        updated = row is not None
        if row is None:
            row = connection.execute(
                f"SELECT {SELECT_OPERATION_COLUMNS} FROM api_operations WHERE operation_id = %s;",
                (operation_id,),
            ).fetchone()
        if updated and result.accepted:
            enqueue_completed_import(
                connection,
                operation_id=operation_id,
                import_status=result.status,
                total_rows=result.total_rows,
                inserted_rows=result.inserted_rows,
                existing_rows=result.existing_rows,
            )
    if row is None:
        raise psycopg.DatabaseError
    return operation_from_row(row)


def get_operation(database_url: str, operation_id: uuid.UUID) -> StoredOperation | None:
    with connect(database_url) as connection, connection.transaction():
        require_current_schema(connection)
        row = connection.execute(
            f"SELECT {SELECT_OPERATION_COLUMNS} FROM api_operations WHERE operation_id = %s;",
            (operation_id,),
        ).fetchone()
    return operation_from_row(row) if row is not None else None
