import json
import time
from pathlib import Path

from fde_foundation.validation import validate_csv, write_report

HEADER = "email,first_name,last_name,phone,source\n"


def write_csv(path: Path, rows: str, *, header: str = HEADER) -> Path:
    path.write_text(header + rows, encoding="utf-8")
    return path


def test_valid_file_is_accepted(tmp_path: Path) -> None:
    csv_path = write_csv(
        tmp_path / "customers.csv",
        "alice@example.com,Alice,Rivera,+14075550101,partner\n"
        "bob@example.com,Bob,Smith,,internal\n",
    )

    result = validate_csv(csv_path)

    assert result.accepted is True
    assert result.total_rows == 2
    assert result.valid_rows == 2
    assert result.issues == []
    assert [record.email for record in result.records] == [
        "alice@example.com",
        "bob@example.com",
    ]


def test_duplicate_email_rejects_entire_batch(tmp_path: Path) -> None:
    csv_path = write_csv(
        tmp_path / "customers.csv",
        "Alice@Example.com,Alice,Rivera,+14075550101,partner\n"
        " alice@example.com ,Alicia,Rivera,+14075550102,event\n",
    )

    result = validate_csv(csv_path)

    assert result.accepted is False
    assert result.records == []
    assert any(item.code == "duplicate_in_file" and item.row == 3 for item in result.issues)


def test_unexpected_column_is_rejected_before_rows_are_read(tmp_path: Path) -> None:
    csv_path = write_csv(
        tmp_path / "customers.csv",
        "alice@example.com,Alice,Rivera,+14075550101,partner,private note\n",
        header="email,first_name,last_name,phone,source,notes\n",
    )

    result = validate_csv(csv_path)

    assert result.accepted is False
    assert result.total_rows == 0
    assert result.issues[0].code == "unexpected_columns"


def test_row_limit_rejects_batch(tmp_path: Path) -> None:
    csv_path = write_csv(
        tmp_path / "customers.csv",
        "alice@example.com,Alice,Rivera,+14075550101,partner\n"
        "bob@example.com,Bob,Smith,+14075550102,internal\n",
    )

    result = validate_csv(csv_path, max_rows=1)

    assert result.accepted is False
    assert any(item.code == "too_many_rows" for item in result.issues)


def test_invalid_fields_are_reported_by_row_without_partial_records(tmp_path: Path) -> None:
    csv_path = write_csv(
        tmp_path / "customers.csv",
        "not-an-email,,Rivera,4075550101,\n",
    )

    result = validate_csv(csv_path)
    fields_with_errors = {item.field for item in result.issues}

    assert result.accepted is False
    assert result.records == []
    assert fields_with_errors == {"email", "first_name", "phone", "source"}


def test_report_does_not_expose_received_values(tmp_path: Path) -> None:
    sensitive_email = "private.person@example.com"
    sensitive_phone = "+14075550199"
    csv_path = write_csv(
        tmp_path / "customers.csv",
        f"{sensitive_email},,Rivera,{sensitive_phone},partner\n",
    )
    report_path = tmp_path / "report.json"

    result = validate_csv(csv_path)
    write_report(result, report_path)
    report_text = report_path.read_text(encoding="utf-8")

    assert json.loads(report_text)["accepted"] is False
    assert sensitive_email not in report_text
    assert sensitive_phone not in report_text


def test_ten_thousand_rows_finish_within_operational_budget(tmp_path: Path) -> None:
    rows = "".join(
        f"customer{index}@example.com,First,Last,,benchmark\n" for index in range(10_000)
    )
    csv_path = write_csv(tmp_path / "customers.csv", rows)

    started_at = time.monotonic()
    result = validate_csv(csv_path)
    elapsed_seconds = time.monotonic() - started_at

    assert result.accepted is True
    assert result.total_rows == 10_000
    assert elapsed_seconds < 30
