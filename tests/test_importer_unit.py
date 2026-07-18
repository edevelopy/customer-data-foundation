import json
from pathlib import Path

from fde_foundation.importer import import_csv


def test_invalid_csv_is_rejected_before_database_connection(tmp_path: Path) -> None:
    csv_path = tmp_path / "invalid.csv"
    csv_path.write_text(
        "email,first_name,last_name,phone,source\nnot-an-email,Alice,Rivera,+14075550101,partner\n",
        encoding="utf-8",
    )

    result = import_csv(csv_path, "postgresql://invalid@127.0.0.1:1/never_contacted")

    assert result.accepted is False
    assert result.status == "validation_failed"
    assert result.issues[0].code == "invalid_format"


def test_database_failure_report_does_not_expose_connection_url(tmp_path: Path) -> None:
    csv_path = tmp_path / "valid.csv"
    csv_path.write_text(
        "email,first_name,last_name,phone,source\n"
        "alice@example.com,Alice,Rivera,+14075550101,partner\n",
        encoding="utf-8",
    )
    secret_url = "postgresql://secret-user:secret-password@127.0.0.1:1/private"

    result = import_csv(csv_path, secret_url)
    report = json.dumps(result.to_report())

    assert result.status == "database_error"
    assert "secret-user" not in report
    assert "secret-password" not in report
    assert secret_url not in report
