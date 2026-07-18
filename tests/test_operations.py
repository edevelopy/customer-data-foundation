from __future__ import annotations

from pathlib import Path

from fde_foundation.operations import (
    OperationalSnapshot,
    evaluate_alerts,
    render_prometheus,
)


def snapshot(**overrides: int | float) -> OperationalSnapshot:
    values: dict[str, int | float] = {
        "imports_total": 4,
        "imports_processing": 0,
        "imports_failed": 1,
        "expired_processing": 0,
        "outbox_pending": 0,
        "outbox_delivering": 0,
        "outbox_delivered": 3,
        "outbox_dead_letter": 0,
        "oldest_pending_seconds": 0.0,
    }
    values.update(overrides)
    return OperationalSnapshot(**values)  # type: ignore[arg-type]


def test_prometheus_metrics_are_bounded_and_contain_no_labels() -> None:
    output = render_prometheus(snapshot())

    assert "fde_imports_total 4" in output
    assert "fde_outbox_delivered 3" in output
    assert "{" not in output
    assert "@" not in output


def test_alerts_detect_recovery_dead_letter_and_delay() -> None:
    alerts = evaluate_alerts(
        snapshot(
            expired_processing=1,
            outbox_dead_letter=2,
            oldest_pending_seconds=301.0,
        ),
        pending_warning_seconds=300,
    )

    assert [(alert.code, alert.severity) for alert in alerts] == [
        ("expired_processing_lease", "critical"),
        ("outbox_dead_letter", "critical"),
        ("outbox_delivery_delayed", "warning"),
    ]


def test_prometheus_alert_contract_covers_every_operator_alert() -> None:
    rules = (Path(__file__).resolve().parents[1] / "deploy" / "prometheus-alerts.yml").read_text(
        encoding="utf-8"
    )

    for metric in (
        "fde_imports_expired_processing",
        "fde_outbox_dead_letter",
        "fde_outbox_oldest_pending_seconds",
    ):
        assert metric in rules
