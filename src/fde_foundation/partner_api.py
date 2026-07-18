"""API socia simulada que verifica webhooks firmados e idempotentes."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Annotated, Literal

import psycopg
import uvicorn
from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from fde_foundation.database import SchemaNotCurrentError, require_current_schema
from fde_foundation.integration_store import EVENT_SCHEMA_VERSION, EVENT_TYPE, connect
from fde_foundation.integration_worker import signature
from fde_foundation.settings import ConfigurationError

MAX_CLOCK_SKEW_SECONDS = 5 * 60
MAX_EVENT_BYTES = 16 * 1024


@dataclass(frozen=True)
class PartnerSettings:
    database_url: str
    webhook_secret: str
    api_host: str
    api_port: int
    simulated_failures: int

    @classmethod
    def from_environment(cls) -> PartnerSettings:
        database_url = os.environ.get("PARTNER_DATABASE_URL") or os.environ.get("DATABASE_URL", "")
        webhook_secret = os.environ.get("PARTNER_WEBHOOK_SECRET", "")
        api_host = os.environ.get("PARTNER_API_HOST", "127.0.0.1")
        try:
            api_port = int(os.environ.get("PARTNER_API_PORT", "8001"))
            simulated_failures = int(os.environ.get("PARTNER_SIMULATED_FAILURES", "0"))
        except ValueError as error:
            raise ConfigurationError from error
        if not database_url or len(webhook_secret) < 32:
            raise ConfigurationError
        if not 1 <= api_port <= 65535 or not 0 <= simulated_failures <= 20:
            raise ConfigurationError
        return cls(
            database_url=database_url,
            webhook_secret=webhook_secret,
            api_host=api_host,
            api_port=api_port,
            simulated_failures=simulated_failures,
        )


def partner_settings() -> PartnerSettings:
    try:
        return PartnerSettings.from_environment()
    except ConfigurationError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "partner_not_ready", "message": "Partner is not ready."},
        ) from error


class PartnerEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"]
    event_id: uuid.UUID
    event_type: Literal["customer_import.completed"]
    occurred_at: datetime
    operation_id: uuid.UUID
    status: Literal["imported", "already_imported"]
    total_rows: int = Field(ge=0)
    inserted_rows: int = Field(ge=0)
    existing_rows: int = Field(ge=0)


class ReceiptResponse(BaseModel):
    event_id: uuid.UUID
    accepted: bool
    duplicate: bool


partner_app = FastAPI(
    title="Simulated Partner API",
    version="0.1.0",
    description="Minimal signed and idempotent webhook receiver for contract testing.",
)


def safe_error(status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"code": code, "message": message})


def verify_signature(secret: str, timestamp: str, supplied_signature: str, body: bytes) -> None:
    try:
        timestamp_seconds = int(timestamp)
    except ValueError as error:
        raise safe_error(400, "invalid_timestamp", "Webhook timestamp is invalid.") from error
    if abs(int(time.time()) - timestamp_seconds) > MAX_CLOCK_SKEW_SECONDS:
        raise safe_error(401, "expired_signature", "Webhook signature has expired.")
    expected = signature(secret, timestamp, body)
    if not hmac.compare_digest(expected, supplied_signature):
        raise safe_error(401, "invalid_signature", "Webhook signature is invalid.")


def record_partner_delivery(
    settings: PartnerSettings, event: PartnerEvent, body_sha256: str
) -> tuple[str, bool]:
    with (
        connect(settings.database_url, application_name="fde-partner-api") as connection,
        connection.transaction(),
    ):
        require_current_schema(connection)
        existing = connection.execute(
            "SELECT body_sha256 FROM partner_receipts WHERE event_id = %s;",
            (event.event_id,),
        ).fetchone()
        if existing is not None:
            if existing[0] != body_sha256:
                return "conflict", False
            return "accepted", True

        attempt = connection.execute(
            """
                INSERT INTO partner_delivery_attempts (event_id, attempt_count)
                VALUES (%s, 1)
                ON CONFLICT (event_id) DO UPDATE
                    SET attempt_count = partner_delivery_attempts.attempt_count + 1,
                        updated_at = now()
                RETURNING attempt_count;
                """,
            (event.event_id,),
        ).fetchone()
        if attempt is None:
            raise psycopg.DatabaseError
        if attempt[0] <= settings.simulated_failures:
            return "transient_failure", False

        connection.execute(
            "INSERT INTO partner_receipts (event_id, body_sha256) VALUES (%s, %s);",
            (event.event_id, body_sha256),
        )
    return "accepted", False


@partner_app.get("/health/live", tags=["health"])
def live() -> dict[str, str]:
    return {"status": "ok"}


@partner_app.get("/health/ready", tags=["health"])
def ready(settings: Annotated[PartnerSettings, Depends(partner_settings)]) -> dict[str, str]:
    try:
        with (
            connect(settings.database_url, application_name="fde-partner-api") as connection,
            connection.transaction(),
        ):
            require_current_schema(connection)
            connection.execute("SELECT 1;")
    except (psycopg.Error, SchemaNotCurrentError) as error:
        raise safe_error(503, "partner_not_ready", "Partner is not ready.") from error
    return {"status": "ready"}


@partner_app.post(
    "/partner/v1/import-events",
    response_model=ReceiptResponse,
    responses={400: {}, 401: {}, 409: {}, 422: {}, 503: {}},
    tags=["webhooks"],
)
async def receive_import_event(
    request: Request,
    settings: Annotated[PartnerSettings, Depends(partner_settings)],
    event_id_header: Annotated[str | None, Header(alias="X-FDE-Event-Id")] = None,
    timestamp_header: Annotated[str | None, Header(alias="X-FDE-Timestamp")] = None,
    signature_header: Annotated[str | None, Header(alias="X-FDE-Signature")] = None,
    idempotency_header: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> ReceiptResponse | JSONResponse:
    if not all((event_id_header, timestamp_header, signature_header, idempotency_header)):
        raise safe_error(400, "missing_webhook_headers", "Required webhook headers are missing.")
    body = await request.body()
    if len(body) > MAX_EVENT_BYTES:
        raise safe_error(413, "event_too_large", "Webhook event is too large.")
    verify_signature(settings.webhook_secret, timestamp_header, signature_header, body)
    try:
        event = PartnerEvent.model_validate(json.loads(body))
    except (json.JSONDecodeError, ValidationError) as error:
        raise safe_error(422, "invalid_event", "Webhook event is invalid.") from error
    if str(event.event_id) not in {event_id_header, idempotency_header} or (
        event_id_header != idempotency_header
    ):
        raise safe_error(409, "event_identity_mismatch", "Webhook event identity is inconsistent.")
    if event.schema_version != EVENT_SCHEMA_VERSION or event.event_type != EVENT_TYPE:
        raise safe_error(422, "unsupported_event", "Webhook event contract is unsupported.")
    body_sha256 = hashlib.sha256(body).hexdigest()
    try:
        outcome, duplicate = record_partner_delivery(settings, event, body_sha256)
    except (psycopg.Error, SchemaNotCurrentError) as error:
        raise safe_error(
            503, "partner_unavailable", "Partner is temporarily unavailable."
        ) from error
    if outcome == "transient_failure":
        return JSONResponse(
            status_code=503,
            content={"detail": {"code": "simulated_failure", "message": "Retry later."}},
            headers={"Retry-After": "1"},
        )
    if outcome == "conflict":
        raise safe_error(409, "event_id_reused", "Event identifier was reused for another body.")
    return ReceiptResponse(event_id=event.event_id, accepted=True, duplicate=duplicate)


def run() -> None:
    try:
        settings = PartnerSettings.from_environment()
    except ConfigurationError as error:
        raise SystemExit("Partner API configuration is incomplete.") from error
    uvicorn.run(
        partner_app,
        host=settings.api_host,
        port=settings.api_port,
        access_log=False,
        log_config=None,
    )


if __name__ == "__main__":
    run()
