import json
from io import StringIO

from fde_foundation.observability import build_ai_event, build_import_event, emit_json_event


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


def test_ai_event_excludes_question_answer_and_provider_key() -> None:
    event = build_ai_event(
        request_id="9d41bb73-0764-481d-a536-df5471943f0d",
        status="completed",
        model="gpt-test",
        prompt_id="enterprise_query_planner",
        prompt_version="1.0.0",
        duration_ms=125,
        input_tokens=20,
        output_tokens=10,
        estimated_cost_usd="0.00000400",
    )

    assert set(event) == {
        "event_type",
        "request_id",
        "status",
        "model",
        "prompt_id",
        "prompt_version",
        "duration_ms",
        "input_tokens",
        "output_tokens",
        "estimated_cost_usd",
    }
    assert "question" not in event
    assert "answer" not in event
    assert "api_key" not in event
