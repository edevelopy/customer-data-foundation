"""Metricas operacionales y alertas derivadas sin exponer datos de clientes."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from typing import Final

import psycopg

from fde_foundation.database import (
    CONNECT_TIMEOUT_SECONDS,
    POSTGRES_OPERATION_LIMITS,
    require_current_schema,
)
from fde_foundation.settings import ConfigurationError, read_secret

METRIC_CONTENT_TYPE: Final = "text/plain; version=0.0.4; charset=utf-8"


@dataclass(frozen=True)
class OperationalSnapshot:
    imports_total: int
    imports_processing: int
    imports_failed: int
    expired_processing: int
    outbox_pending: int
    outbox_delivering: int
    outbox_delivered: int
    outbox_dead_letter: int
    oldest_pending_seconds: float


@dataclass(frozen=True)
class Alert:
    code: str
    severity: str
    value: float


def collect_snapshot(database_url: str) -> OperationalSnapshot:
    with psycopg.connect(
        database_url,
        connect_timeout=CONNECT_TIMEOUT_SECONDS,
        options=POSTGRES_OPERATION_LIMITS,
        application_name="fde-operations",
    ) as connection:
        require_current_schema(connection)
        import_row = connection.execute(
            """
            SELECT
                count(*),
                count(*) FILTER (WHERE status = 'processing'),
                count(*) FILTER (
                    WHERE status IN ('validation_failed', 'conflict',
                                     'configuration_error', 'migration_required', 'database_error')
                ),
                count(*) FILTER (
                    WHERE status = 'processing' AND lease_expires_at <= now()
                )
            FROM api_operations;
            """
        ).fetchone()
        outbox_row = connection.execute(
            """
            SELECT
                count(*) FILTER (WHERE status = 'pending'),
                count(*) FILTER (WHERE status = 'delivering'),
                count(*) FILTER (WHERE status = 'delivered'),
                count(*) FILTER (WHERE status = 'dead_letter'),
                coalesce(
                    extract(
                        epoch FROM now() - min(created_at)
                            FILTER (WHERE status IN ('pending', 'delivering'))
                    ),
                    0
                )
            FROM integration_outbox;
            """
        ).fetchone()
    if import_row is None or outbox_row is None:
        raise psycopg.DatabaseError
    return OperationalSnapshot(
        imports_total=int(import_row[0]),
        imports_processing=int(import_row[1]),
        imports_failed=int(import_row[2]),
        expired_processing=int(import_row[3]),
        outbox_pending=int(outbox_row[0]),
        outbox_delivering=int(outbox_row[1]),
        outbox_delivered=int(outbox_row[2]),
        outbox_dead_letter=int(outbox_row[3]),
        oldest_pending_seconds=max(0.0, float(outbox_row[4])),
    )


def render_prometheus(snapshot: OperationalSnapshot) -> str:
    metrics = (
        ("fde_imports_total", snapshot.imports_total, "Import operations persisted."),
        ("fde_imports_processing", snapshot.imports_processing, "Imports currently processing."),
        ("fde_imports_failed", snapshot.imports_failed, "Imports with a safe failure status."),
        (
            "fde_imports_expired_processing",
            snapshot.expired_processing,
            "Processing imports with an expired recovery lease.",
        ),
        ("fde_outbox_pending", snapshot.outbox_pending, "Partner events pending delivery."),
        (
            "fde_outbox_delivering",
            snapshot.outbox_delivering,
            "Partner events with an active delivery lease.",
        ),
        ("fde_outbox_delivered", snapshot.outbox_delivered, "Partner events delivered."),
        (
            "fde_outbox_dead_letter",
            snapshot.outbox_dead_letter,
            "Partner events requiring operator intervention.",
        ),
        (
            "fde_outbox_oldest_pending_seconds",
            round(snapshot.oldest_pending_seconds, 3),
            "Age in seconds of the oldest undelivered partner event.",
        ),
    )
    lines: list[str] = []
    for name, value, help_text in metrics:
        lines.extend((f"# HELP {name} {help_text}", f"# TYPE {name} gauge", f"{name} {value}"))
    return "\n".join(lines) + "\n"


def evaluate_alerts(
    snapshot: OperationalSnapshot, *, pending_warning_seconds: int = 300
) -> list[Alert]:
    alerts: list[Alert] = []
    if snapshot.expired_processing:
        alerts.append(
            Alert("expired_processing_lease", "critical", float(snapshot.expired_processing))
        )
    if snapshot.outbox_dead_letter:
        alerts.append(Alert("outbox_dead_letter", "critical", float(snapshot.outbox_dead_letter)))
    if snapshot.oldest_pending_seconds >= pending_warning_seconds:
        alerts.append(Alert("outbox_delivery_delayed", "warning", snapshot.oldest_pending_seconds))
    return alerts


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pending-warning-seconds", type=int, default=300)
    parser.add_argument("--format", choices=("json", "prometheus"), default="json")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not 1 <= args.pending_warning_seconds <= 86400:
        raise SystemExit("Operational threshold is invalid.")
    try:
        database_url = read_secret("DATABASE_URL", minimum_length=1)
        snapshot = collect_snapshot(database_url)
    except (ConfigurationError, psycopg.Error) as error:
        raise SystemExit("Operational snapshot is unavailable.") from error
    alerts = evaluate_alerts(snapshot, pending_warning_seconds=args.pending_warning_seconds)
    if args.format == "prometheus":
        print(render_prometheus(snapshot), end="")
    else:
        print(
            json.dumps(
                {
                    "alerts": [asdict(alert) for alert in alerts],
                    "snapshot": asdict(snapshot),
                    "status": "alert" if alerts else "healthy",
                },
                separators=(",", ":"),
                sort_keys=True,
            )
        )
    return int(bool(alerts))


if __name__ == "__main__":
    raise SystemExit(main())
