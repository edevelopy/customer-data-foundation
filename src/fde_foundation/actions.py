"""Controlled simulated actions with separation of request, approval, and execution."""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from datetime import datetime
from typing import Literal, Protocol

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from pydantic import BaseModel, ConfigDict, Field

from fde_foundation.api_store import protected_hash
from fde_foundation.database import require_current_schema

ACTION_TOOL_NAME: Literal["send_customer_followup"] = "send_customer_followup"


class ActionNotFoundError(Exception):
    pass


class ActionTransitionError(Exception):
    pass


class SelfApprovalError(Exception):
    pass


class ActionRateLimitError(Exception):
    pass


class ActionArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")

    customer_reference: str = Field(pattern=r"^CUST-[A-Z0-9]{3,32}$")
    template: Literal["case_update", "information_request", "resolution_notice"]
    reason: Literal["status_update", "information_requested", "case_resolved"]


class PlannedAction(BaseModel):
    action_type: Literal["send_customer_followup"] = ACTION_TOOL_NAME
    arguments: ActionArguments
    provider: str
    model: str
    provider_response_id: str


class ActionPlanner(Protocol):
    def plan(self, instruction: str, *, request_id: str) -> PlannedAction: ...


class ActionRecord(BaseModel):
    action_id: uuid.UUID
    action_type: Literal["send_customer_followup"]
    arguments: ActionArguments
    arguments_sha256: str
    status: Literal["pending", "approved", "executed", "rejected", "expired"]
    planner_provider: str
    planner_model: str
    requester_hash: str = Field(exclude=True)
    approver_hash: str | None = Field(default=None, exclude=True)
    result_code: str | None
    created_at: datetime
    approved_at: datetime | None
    executed_at: datetime | None


class DeterministicActionPlanner:
    """Strict local parser for tests; it never calls or executes a tool."""

    name = "deterministic_local"
    model = "controlled-parser-v1"

    def plan(self, instruction: str, *, request_id: str) -> PlannedAction:
        reference = re.search(r"\bCUST-[A-Z0-9]{3,32}\b", instruction.upper())
        template = next(
            (
                value
                for value in ("case_update", "information_request", "resolution_notice")
                if value in instruction
            ),
            None,
        )
        reason = next(
            (
                value
                for value in ("status_update", "information_requested", "case_resolved")
                if value in instruction
            ),
            None,
        )
        if reference is None or template is None or reason is None:
            raise ValueError("The local action instruction is not explicit enough.")
        return PlannedAction(
            arguments=ActionArguments(
                customer_reference=reference.group(0),
                template=template,  # type: ignore[arg-type]
                reason=reason,  # type: ignore[arg-type]
            ),
            provider=self.name,
            model=self.model,
            provider_response_id=f"local-{request_id}",
        )


def _canonical_arguments(arguments: ActionArguments) -> tuple[dict[str, str], str]:
    values = arguments.model_dump(mode="json")
    canonical = json.dumps(values, sort_keys=True, separators=(",", ":"))
    return values, hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _record(row: dict[str, object]) -> ActionRecord:
    return ActionRecord.model_validate(row)


def enforce_action_rate_limit(
    *,
    database_url: str,
    identifier_hash_key: str,
    actor_subject: str,
    requests_per_minute: int,
) -> None:
    if not 1 <= requests_per_minute <= 1000:
        raise ValueError("Action rate limit is invalid.")
    actor_hash = protected_hash(identifier_hash_key, "action-principal", actor_subject)
    with psycopg.connect(database_url, row_factory=dict_row) as connection:
        require_current_schema(connection)
        row = connection.execute(
            """
            SELECT count(*) AS total FROM action_requests
            WHERE requester_hash = %s AND created_at >= now() - interval '1 minute'
            """,
            (actor_hash,),
        ).fetchone()
    if row and int(row["total"]) >= requests_per_minute:
        raise ActionRateLimitError


def create_action_request(
    *,
    database_url: str,
    identifier_hash_key: str,
    actor_subject: str,
    planned: PlannedAction,
) -> ActionRecord:
    actor_hash = protected_hash(identifier_hash_key, "action-principal", actor_subject)
    values, arguments_sha256 = _canonical_arguments(planned.arguments)
    action_id = uuid.uuid4()
    with psycopg.connect(database_url, row_factory=dict_row) as connection:
        require_current_schema(connection)
        row = connection.execute(
            """
            INSERT INTO action_requests (
                action_id, requester_hash, action_type, arguments, arguments_sha256,
                status, planner_provider, planner_model
            ) VALUES (%s, %s, %s, %s, %s, 'pending', %s, %s)
            RETURNING *
            """,
            (
                action_id,
                actor_hash,
                planned.action_type,
                Jsonb(values),
                arguments_sha256,
                planned.provider,
                planned.model,
            ),
        ).fetchone()
        connection.execute(
            """
            INSERT INTO action_audit_events (
                event_id, action_id, actor_hash, event_type, arguments_sha256
            ) VALUES (%s, %s, %s, 'proposed', %s)
            """,
            (uuid.uuid4(), action_id, actor_hash, arguments_sha256),
        )
    if row is None:
        raise psycopg.DatabaseError
    return _record(row)


def get_action(*, database_url: str, action_id: uuid.UUID) -> ActionRecord | None:
    with psycopg.connect(database_url, row_factory=dict_row) as connection:
        require_current_schema(connection)
        row = connection.execute(
            "SELECT * FROM action_requests WHERE action_id = %s", (action_id,)
        ).fetchone()
    return _record(row) if row else None


def approve_action(
    *,
    database_url: str,
    identifier_hash_key: str,
    approver_subject: str,
    action_id: uuid.UUID,
) -> ActionRecord:
    approver_hash = protected_hash(identifier_hash_key, "action-principal", approver_subject)
    with (
        psycopg.connect(database_url, row_factory=dict_row) as connection,
        connection.transaction(),
    ):
        require_current_schema(connection)
        current = connection.execute(
            "SELECT * FROM action_requests WHERE action_id = %s FOR UPDATE", (action_id,)
        ).fetchone()
        if current is None:
            raise ActionNotFoundError
        if current["requester_hash"] == approver_hash:
            raise SelfApprovalError
        if current["status"] == "approved" and current["approver_hash"] == approver_hash:
            return _record(current)
        if current["status"] != "pending":
            raise ActionTransitionError
        row = connection.execute(
            """
            UPDATE action_requests
            SET status = 'approved', approver_hash = %s, approved_at = now()
            WHERE action_id = %s
            RETURNING *
            """,
            (approver_hash, action_id),
        ).fetchone()
        connection.execute(
            """
            INSERT INTO action_audit_events (
                event_id, action_id, actor_hash, event_type, arguments_sha256
            ) VALUES (%s, %s, %s, 'approved', %s)
            """,
            (uuid.uuid4(), action_id, approver_hash, current["arguments_sha256"]),
        )
    if row is None:
        raise psycopg.DatabaseError
    return _record(row)


def execute_action(
    *,
    database_url: str,
    identifier_hash_key: str,
    executor_subject: str,
    action_id: uuid.UUID,
) -> ActionRecord:
    executor_hash = protected_hash(identifier_hash_key, "action-principal", executor_subject)
    with (
        psycopg.connect(database_url, row_factory=dict_row) as connection,
        connection.transaction(),
    ):
        require_current_schema(connection)
        current = connection.execute(
            "SELECT * FROM action_requests WHERE action_id = %s FOR UPDATE", (action_id,)
        ).fetchone()
        if current is None:
            raise ActionNotFoundError
        if current["status"] == "executed":
            return _record(current)
        if current["status"] != "approved":
            raise ActionTransitionError
        result_code = "simulated_followup_queued"
        row = connection.execute(
            """
            UPDATE action_requests
            SET status = 'executed', executed_at = now(), result_code = %s
            WHERE action_id = %s
            RETURNING *
            """,
            (result_code, action_id),
        ).fetchone()
        connection.execute(
            """
            INSERT INTO action_audit_events (
                event_id, action_id, actor_hash, event_type, arguments_sha256, result_code
            ) VALUES (%s, %s, %s, 'executed', %s, %s)
            """,
            (
                uuid.uuid4(),
                action_id,
                executor_hash,
                current["arguments_sha256"],
                result_code,
            ),
        )
    if row is None:
        raise psycopg.DatabaseError
    return _record(row)
