from __future__ import annotations

import json
import os
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace

import jwt
import psycopg
import pytest
from fastapi.testclient import TestClient
from openai.types.responses import ResponseFunctionToolCall

from fde_foundation.actions import (
    ActionRateLimitError,
    ActionTransitionError,
    DeterministicActionPlanner,
    SelfApprovalError,
    approve_action,
    create_action_request,
    enforce_action_rate_limit,
    execute_action,
)
from fde_foundation.api import app
from fde_foundation.database import upgrade_database
from fde_foundation.openai_action_provider import OpenAIActionPlanner
from fde_foundation.settings import AISettings

DATABASE_URL = "postgresql://fde_test:test-only-password@localhost:55435/fde_test"
HASH_KEY = "test-action-hash-key-with-more-than-thirty-two-characters"
JWT_SECRET = "test-jwt-signing-key-with-more-than-thirty-two-characters"
JWT_ISSUER = "fde-test"
JWT_AUDIENCE = "fde-actions-test"


@pytest.fixture
def database_url() -> str:
    url = os.environ.get("PHASE4_TEST_DATABASE_URL", DATABASE_URL)
    upgrade_database(url)
    with psycopg.connect(url) as connection:
        connection.execute("TRUNCATE action_audit_events, action_requests CASCADE")
    return url


def planned():
    return DeterministicActionPlanner().plan(
        "Send CUST-ABC123 using case_update because status_update", request_id="request-1"
    )


@pytest.mark.integration
def test_action_requires_separate_approval_and_execution_is_idempotent(database_url: str) -> None:
    pending = create_action_request(
        database_url=database_url,
        identifier_hash_key=HASH_KEY,
        actor_subject="operator-one",
        planned=planned(),
    )

    with pytest.raises(ActionTransitionError):
        execute_action(
            database_url=database_url,
            identifier_hash_key=HASH_KEY,
            executor_subject="operator-one",
            action_id=pending.action_id,
        )
    with pytest.raises(SelfApprovalError):
        approve_action(
            database_url=database_url,
            identifier_hash_key=HASH_KEY,
            approver_subject="operator-one",
            action_id=pending.action_id,
        )
    approved = approve_action(
        database_url=database_url,
        identifier_hash_key=HASH_KEY,
        approver_subject="auditor-two",
        action_id=pending.action_id,
    )
    executed = execute_action(
        database_url=database_url,
        identifier_hash_key=HASH_KEY,
        executor_subject="operator-one",
        action_id=pending.action_id,
    )
    replay = execute_action(
        database_url=database_url,
        identifier_hash_key=HASH_KEY,
        executor_subject="operator-one",
        action_id=pending.action_id,
    )

    assert pending.status == "pending"
    assert approved.status == "approved"
    assert executed.status == "executed"
    assert executed.result_code == "simulated_followup_queued"
    assert replay.executed_at == executed.executed_at
    with psycopg.connect(database_url, row_factory=psycopg.rows.dict_row) as connection:
        events = connection.execute(
            "SELECT * FROM action_audit_events ORDER BY created_at"
        ).fetchall()
    assert [event["event_type"] for event in events] == ["proposed", "approved", "executed"]
    assert len({event["arguments_sha256"] for event in events}) == 1
    assert all(len(event["actor_hash"]) == 64 for event in events)


@pytest.mark.integration
def test_action_rate_limit_blocks_before_another_plan(database_url: str) -> None:
    create_action_request(
        database_url=database_url,
        identifier_hash_key=HASH_KEY,
        actor_subject="operator-one",
        planned=planned(),
    )

    with pytest.raises(ActionRateLimitError):
        enforce_action_rate_limit(
            database_url=database_url,
            identifier_hash_key=HASH_KEY,
            actor_subject="operator-one",
            requests_per_minute=1,
        )


def token(subject: str, roles: list[str]) -> str:
    now = datetime.now(UTC)
    return jwt.encode(
        {
            "sub": subject,
            "roles": roles,
            "iss": JWT_ISSUER,
            "aud": JWT_AUDIENCE,
            "iat": now,
            "exp": now + timedelta(minutes=10),
        },
        JWT_SECRET,
        algorithm="HS256",
    )


def auth(subject: str, roles: list[str]) -> dict[str, str]:
    return {"Authorization": f"Bearer {token(subject, roles)}"}


@pytest.fixture
def api_client(database_url: str, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("JWT_SECRET", JWT_SECRET)
    monkeypatch.setenv("IDENTIFIER_HASH_KEY", HASH_KEY)
    monkeypatch.setenv("METRICS_TOKEN", "metrics-token-with-more-than-thirty-two-characters")
    monkeypatch.setenv("JWT_ISSUER", JWT_ISSUER)
    monkeypatch.setenv("JWT_AUDIENCE", JWT_AUDIENCE)
    monkeypatch.setenv("ACTION_PROVIDER", "deterministic_local")
    monkeypatch.setenv("ACTION_RATE_LIMIT_PER_MINUTE", "5")
    with TestClient(app) as client:
        yield client


@pytest.mark.integration
def test_http_action_flow_requires_a_different_auditor(api_client: TestClient) -> None:
    proposed = api_client.post(
        "/v1/assistant/action-plans",
        headers=auth("operator-one", ["operator", "auditor"]),
        json={"instruction": "Send CUST-ABC123 using case_update because status_update"},
    )
    action_id = proposed.json()["action_id"]
    early = api_client.post(
        f"/v1/actions/{action_id}/execute",
        headers=auth("operator-one", ["operator"]),
    )
    self_approval = api_client.post(
        f"/v1/actions/{action_id}/approve",
        headers=auth("operator-one", ["auditor"]),
    )
    approved = api_client.post(
        f"/v1/actions/{action_id}/approve",
        headers=auth("auditor-two", ["auditor"]),
    )
    executed = api_client.post(
        f"/v1/actions/{action_id}/execute",
        headers=auth("operator-one", ["operator"]),
    )

    assert proposed.status_code == 200
    assert proposed.json()["status"] == "pending"
    assert "requester_hash" not in proposed.json()
    assert early.status_code == 409
    assert self_approval.status_code == 409
    assert approved.json()["status"] == "approved"
    assert executed.json()["status"] == "executed"
    assert executed.json()["result_code"] == "simulated_followup_queued"


def ai_settings() -> AISettings:
    return AISettings(
        api_key="sk-test-key-with-more-than-twenty-characters",
        model="gpt-test",
        timeout_seconds=10,
        max_retries=1,
        max_output_tokens=250,
        input_cost_per_million_usd=Decimal("2"),
        output_cost_per_million_usd=Decimal("8"),
    )


class FakeResponses:
    def __init__(self, response: SimpleNamespace) -> None:
        self.response = response
        self.kwargs: dict[str, object] = {}

    def create(self, **kwargs: object) -> SimpleNamespace:
        self.kwargs = kwargs
        return self.response


def test_openai_action_planner_uses_one_strict_tool_and_does_not_execute() -> None:
    call = ResponseFunctionToolCall(
        arguments=json.dumps(
            {
                "customer_reference": "CUST-ABC123",
                "template": "case_update",
                "reason": "status_update",
            }
        ),
        call_id="call-1",
        name="send_customer_followup",
        type="function_call",
    )
    responses = FakeResponses(
        SimpleNamespace(id="resp-action", model="gpt-test-2026-07-01", output=[call])
    )
    planner = OpenAIActionPlanner(ai_settings(), client=SimpleNamespace(responses=responses))

    result = planner.plan(
        "Send CUST-ABC123 using case_update because status_update", request_id="request-1"
    )

    tools = responses.kwargs["tools"]
    assert result.arguments.customer_reference == "CUST-ABC123"
    assert responses.kwargs["store"] is False
    assert responses.kwargs["parallel_tool_calls"] is False
    assert isinstance(tools, list)
    assert tools[0]["strict"] is True
    assert tools[0]["parameters"]["additionalProperties"] is False
    assert "execute" not in responses.kwargs
