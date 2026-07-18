"""Importacion transaccional e idempotente de clientes en PostgreSQL."""

from __future__ import annotations

import argparse
import hashlib
import os
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Final

import psycopg

from fde_foundation.validation import (
    ValidatedCustomer,
    ValidationIssue,
    issue,
    validate_csv,
    write_json_report,
)

SCHEMA_SQL: Final = """
CREATE TABLE IF NOT EXISTS import_batches (
    id uuid PRIMARY KEY,
    file_sha256 char(64) NOT NULL UNIQUE,
    row_count integer NOT NULL CHECK (row_count >= 0),
    inserted_count integer NOT NULL CHECK (inserted_count >= 0),
    existing_count integer NOT NULL CHECK (existing_count >= 0),
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS customers (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    email varchar(254) NOT NULL UNIQUE,
    first_name varchar(80) NOT NULL,
    last_name varchar(80) NOT NULL,
    phone varchar(16) NOT NULL DEFAULT '',
    source varchar(50) NOT NULL,
    import_batch_id uuid NOT NULL REFERENCES import_batches(id),
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT customers_email_normalized CHECK (email = lower(btrim(email))),
    CONSTRAINT customers_email_shape CHECK (position('@' IN email) > 1),
    CONSTRAINT customers_first_name_nonempty CHECK (length(btrim(first_name)) > 0),
    CONSTRAINT customers_last_name_nonempty CHECK (length(btrim(last_name)) > 0),
    CONSTRAINT customers_phone_e164 CHECK (phone = '' OR phone ~ '^\\+[1-9][0-9]{7,14}$'),
    CONSTRAINT customers_source_nonempty CHECK (length(btrim(source)) > 0)
);
"""

INSERT_BATCH_SQL: Final = """
INSERT INTO import_batches (id, file_sha256, row_count, inserted_count, existing_count)
VALUES (%s, %s, %s, 0, 0)
ON CONFLICT (file_sha256) DO NOTHING
RETURNING id;
"""

INSERT_CUSTOMER_SQL: Final = """
INSERT INTO customers (
    email, first_name, last_name, phone, source, import_batch_id
) VALUES (%s, %s, %s, %s, %s, %s);
"""


@dataclass(frozen=True)
class ImportResult:
    """Resultado seguro: contiene conteos y errores, nunca valores del cliente."""

    accepted: bool
    status: str
    total_rows: int
    inserted_rows: int
    existing_rows: int
    issues: list[ValidationIssue]

    def to_report(self) -> dict[str, object]:
        return {
            "accepted": self.accepted,
            "mode": "strict",
            "status": self.status,
            "summary": {
                "total_rows": self.total_rows,
                "inserted_rows": self.inserted_rows,
                "existing_rows": self.existing_rows,
                "error_count": len(self.issues),
            },
            "issues": [asdict(item) for item in self.issues],
        }


class CustomerConflictsError(Exception):
    """Senal interna que obliga a PostgreSQL a revertir la transaccion."""

    def __init__(self, issues: list[ValidationIssue]) -> None:
        super().__init__("customer conflicts detected")
        self.issues = issues


def database_issue(code: str, message: str, correction: str) -> ValidationIssue:
    return issue(None, "database", code, message, correction)


def calculate_sha256(path: Path) -> str:
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def ensure_schema(database_url: str) -> None:
    """Crea el esquema inicial en una transaccion independiente."""
    with psycopg.connect(
        database_url, connect_timeout=5, application_name="fde-import"
    ) as connection:
        connection.execute(SCHEMA_SQL)


def customer_values(customer: ValidatedCustomer) -> tuple[str, str, str, str]:
    return customer.first_name, customer.last_name, customer.phone, customer.source


def conflict_issues(
    records: list[ValidatedCustomer], existing_by_email: dict[str, tuple[str, str, str, str]]
) -> list[ValidationIssue]:
    conflicts: list[ValidationIssue] = []
    for record in records:
        existing = existing_by_email.get(record.email)
        if existing is not None and existing != customer_values(record):
            conflicts.append(
                issue(
                    record.row_number,
                    "email",
                    "customer_conflict",
                    "El cliente ya existe con datos diferentes.",
                    "Revisa el registro existente antes de intentar una actualizacion.",
                )
            )
    return conflicts


def import_validated_records(
    records: list[ValidatedCustomer], file_sha256: str, database_url: str
) -> ImportResult:
    """Importa registros ya validados dentro de una sola transaccion."""
    total_rows = len(records)
    try:
        ensure_schema(database_url)
        with psycopg.connect(
            database_url, connect_timeout=5, application_name="fde-import"
        ) as connection:
            try:
                with connection.transaction():
                    batch_id = uuid.uuid4()
                    inserted_batch = connection.execute(
                        INSERT_BATCH_SQL, (batch_id, file_sha256, total_rows)
                    ).fetchone()
                    if inserted_batch is None:
                        return ImportResult(
                            True,
                            "already_imported",
                            total_rows,
                            0,
                            total_rows,
                            [],
                        )

                    emails = [record.email for record in records]
                    existing_rows = connection.execute(
                        """
                        SELECT email, first_name, last_name, phone, source
                        FROM customers
                        WHERE email = ANY(%s);
                        """,
                        (emails,),
                    ).fetchall()
                    existing_by_email = {
                        row[0]: (row[1], row[2], row[3], row[4]) for row in existing_rows
                    }
                    conflicts = conflict_issues(records, existing_by_email)
                    if conflicts:
                        raise CustomerConflictsError(conflicts)

                    new_records = [
                        record for record in records if record.email not in existing_by_email
                    ]
                    if new_records:
                        with connection.cursor() as cursor:
                            cursor.executemany(
                                INSERT_CUSTOMER_SQL,
                                [
                                    (
                                        record.email,
                                        record.first_name,
                                        record.last_name,
                                        record.phone,
                                        record.source,
                                        batch_id,
                                    )
                                    for record in new_records
                                ],
                            )

                    inserted_count = len(new_records)
                    existing_count = total_rows - inserted_count
                    connection.execute(
                        """
                        UPDATE import_batches
                        SET inserted_count = %s, existing_count = %s
                        WHERE id = %s;
                        """,
                        (inserted_count, existing_count, batch_id),
                    )
                    return ImportResult(
                        True,
                        "imported",
                        total_rows,
                        inserted_count,
                        existing_count,
                        [],
                    )
            except CustomerConflictsError as error:
                return ImportResult(False, "conflict", total_rows, 0, 0, error.issues)
    except psycopg.Error:
        return ImportResult(
            False,
            "database_error",
            total_rows,
            0,
            0,
            [
                database_issue(
                    "operation_failed",
                    "La operacion de base de datos no pudo completarse.",
                    "Comprueba la disponibilidad y configuracion de PostgreSQL.",
                )
            ],
        )


def import_csv(path: Path, database_url: str) -> ImportResult:
    """Valida primero y solo abre PostgreSQL cuando todo el lote es valido."""
    validation = validate_csv(path)
    if not validation.accepted:
        return ImportResult(
            False,
            "validation_failed",
            validation.total_rows,
            0,
            0,
            validation.issues,
        )
    return import_validated_records(validation.records, calculate_sha256(path), database_url)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv_file", type=Path, help="archivo CSV que se importara")
    parser.add_argument("--report", type=Path, help="ruta opcional para el reporte JSON")
    return parser.parse_args()


def missing_configuration_result() -> ImportResult:
    return ImportResult(
        False,
        "configuration_error",
        0,
        0,
        0,
        [
            database_issue(
                "missing_database_url",
                "Falta la configuracion de PostgreSQL.",
                "Define DATABASE_URL en el entorno local.",
            )
        ],
    )


def main() -> int:
    args = parse_args()
    database_url = os.environ.get("DATABASE_URL")
    result = (
        import_csv(args.csv_file, database_url) if database_url else missing_configuration_result()
    )
    if args.report:
        write_json_report(result.to_report(), args.report)
    print(
        f"accepted={str(result.accepted).lower()} status={result.status} "
        f"rows={result.total_rows} inserted={result.inserted_rows} "
        f"existing={result.existing_rows} errors={len(result.issues)}"
    )
    if result.accepted:
        return 0
    return 2 if result.status in {"configuration_error", "database_error"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
