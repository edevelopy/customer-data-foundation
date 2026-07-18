import json
from io import StringIO

from fde_foundation.observability import build_import_event, emit_json_event


def test_import_event_contains_only_approved_fields() -> None:
    event = build_import_event(
        operation_id="5ba4eaca-f811-49a2-ae0e-9cc20968d491",
        status="conflict",
        duration_ms=42,
        total_rows=2,
        inserted_rows=0,
        existing_rows=0,
        error_codes=["customer_conflict", "customer_conflict"],
    )

    assert set(event) == {
        "operation_id",
        "status",
        "duration_ms",
        "total_rows",
        "inserted_rows",
        "existing_rows",
        "error_codes",
    }
    assert event["error_codes"] == ["customer_conflict"]


def test_emitted_event_is_one_valid_json_line() -> None:
    stream = StringIO()
    event = build_import_event(
        operation_id="5ba4eaca-f811-49a2-ae0e-9cc20968d491",
        status="imported",
        duration_ms=15,
        total_rows=3,
        inserted_rows=3,
        existing_rows=0,
        error_codes=[],
    )

    emit_json_event(event, stream)

    assert stream.getvalue().count("\n") == 1
    assert json.loads(stream.getvalue()) == event
