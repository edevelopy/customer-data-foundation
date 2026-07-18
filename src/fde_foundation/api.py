"""API sincrona y segura para importaciones de clientes."""

from __future__ import annotations

import hashlib
import math
import os
import tempfile
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

import psycopg
import uvicorn
from fastapi import Depends, FastAPI, File, Header, HTTPException, UploadFile, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool
from starlette.requests import Request

from fde_foundation.api_store import (
    StoredOperation,
    complete_operation,
    connect,
    get_operation,
    protected_hash,
    reserve_operation,
)
from fde_foundation.auth import Principal, api_settings, authenticate, require_operator
from fde_foundation.database import (
    RECOVERY_LEASE_SECONDS,
    SchemaNotCurrentError,
    require_current_schema,
)
from fde_foundation.importer import import_csv
from fde_foundation.integration_store import OutboxEvent, get_event_for_operation
from fde_foundation.observability import build_import_event, emit_json_event
from fde_foundation.settings import ConfigurationError, Settings
from fde_foundation.validation import MAX_FILE_BYTES

UPLOAD_CHUNK_BYTES = 64 * 1024


class IssueResponse(BaseModel):
    row: int | None
    field: str
    code: str
    message: str
    correction: str


class OperationResponse(BaseModel):
    operation_id: uuid.UUID
    accepted: bool
    status: str
    total_rows: int
    inserted_rows: int
    existing_rows: int
    duration_ms: int
    attempt_count: int
    error_codes: list[str]
    issues: list[IssueResponse]


class IntegrationResponse(BaseModel):
    event_id: uuid.UUID
    operation_id: uuid.UUID
    event_type: str
    status: str
    attempt_count: int
    available_at: datetime
    last_failure_code: str | None
    delivered_at: datetime | None


def public_operation(operation: StoredOperation) -> OperationResponse:
    return OperationResponse(
        operation_id=operation.operation_id,
        accepted=operation.accepted,
        status=operation.status,
        total_rows=operation.total_rows,
        inserted_rows=operation.inserted_rows,
        existing_rows=operation.existing_rows,
        duration_ms=operation.duration_ms,
        attempt_count=operation.attempt_count,
        error_codes=list(operation.error_codes),
        issues=[IssueResponse.model_validate(item) for item in operation.issues],
    )


def public_integration(event: OutboxEvent) -> IntegrationResponse:
    return IntegrationResponse(
        event_id=event.event_id,
        operation_id=event.operation_id,
        event_type=event.event_type,
        status=event.status,
        attempt_count=event.attempt_count,
        available_at=event.available_at,
        last_failure_code=event.last_failure_code,
        delivered_at=event.delivered_at,
    )


def response_status(operation_status: str) -> int:
    return {
        "processing": status.HTTP_202_ACCEPTED,
        "imported": status.HTTP_200_OK,
        "already_imported": status.HTTP_200_OK,
        "validation_failed": status.HTTP_422_UNPROCESSABLE_CONTENT,
        "conflict": status.HTTP_409_CONFLICT,
        "configuration_error": status.HTTP_503_SERVICE_UNAVAILABLE,
        "migration_required": status.HTTP_503_SERVICE_UNAVAILABLE,
        "database_error": status.HTTP_503_SERVICE_UNAVAILABLE,
    }.get(operation_status, status.HTTP_500_INTERNAL_SERVER_ERROR)


def operation_json_response(operation: StoredOperation) -> JSONResponse:
    model = public_operation(operation)
    headers = None
    if operation.status == "processing":
        remaining_seconds = math.ceil(
            (operation.lease_expires_at - datetime.now(UTC)).total_seconds()
        )
        headers = {"Retry-After": str(max(1, min(remaining_seconds, RECOVERY_LEASE_SECONDS)))}
    return JSONResponse(
        status_code=response_status(operation.status),
        content=model.model_dump(mode="json"),
        headers=headers,
    )


def safe_error(status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"code": code, "message": message})


def validate_idempotency_key(value: str | None) -> str:
    if value is None or not 8 <= len(value) <= 200 or not value.isprintable():
        raise safe_error(
            status.HTTP_400_BAD_REQUEST,
            "invalid_idempotency_key",
            "A valid Idempotency-Key header is required.",
        )
    return value


async def persist_bounded_upload(upload: UploadFile) -> tuple[Path, str]:
    digest = hashlib.sha256()
    total_bytes = 0
    file_descriptor, temporary_name = tempfile.mkstemp(prefix="fde-api-upload-", suffix=".csv")
    path = Path(temporary_name)
    try:
        with os.fdopen(file_descriptor, "wb") as destination:
            while chunk := await upload.read(UPLOAD_CHUNK_BYTES):
                total_bytes += len(chunk)
                if total_bytes > MAX_FILE_BYTES:
                    raise safe_error(
                        status.HTTP_413_CONTENT_TOO_LARGE,
                        "file_too_large",
                        "The CSV exceeds the 10 MiB limit.",
                    )
                digest.update(chunk)
                destination.write(chunk)
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    finally:
        await upload.close()
    return path, digest.hexdigest()


def emit_operation(operation: StoredOperation, *, status_override: str | None = None) -> None:
    emit_json_event(
        build_import_event(
            operation_id=str(operation.operation_id),
            status=status_override or operation.status,
            duration_ms=operation.duration_ms,
            total_rows=operation.total_rows,
            inserted_rows=operation.inserted_rows,
            existing_rows=operation.existing_rows,
            error_codes=operation.error_codes,
        )
    )


app = FastAPI(
    title="Customer Import API",
    version="0.2.0",
    description="Strict imports with durable asynchronous partner notifications.",
)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    _request: Request, _error: RequestValidationError
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content={"detail": {"code": "invalid_request", "message": "Request validation failed."}},
    )


@app.get("/health/live", tags=["health"])
def live() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/ready", tags=["health"])
def ready(settings: Annotated[Settings, Depends(api_settings)]) -> dict[str, str]:
    try:
        with connect(settings.database_url) as connection, connection.transaction():
            require_current_schema(connection)
            connection.execute("SELECT 1;")
    except (psycopg.Error, SchemaNotCurrentError) as error:
        raise safe_error(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "service_not_ready",
            "Service is not ready.",
        ) from error
    return {"status": "ready"}


@app.post(
    "/v1/imports",
    response_model=OperationResponse,
    responses={
        202: {"model": OperationResponse, "description": "Identical request is processing."},
        400: {},
        401: {},
        403: {},
        409: {},
        413: {},
        422: {},
        503: {},
    },
    tags=["imports"],
)
async def create_import(
    file: Annotated[UploadFile, File(description="UTF-8 customer CSV")],
    principal: Annotated[Principal, Depends(require_operator)],
    settings: Annotated[Settings, Depends(api_settings)],
    idempotency_key_header: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> JSONResponse:
    idempotency_key = validate_idempotency_key(idempotency_key_header)
    started_at = time.monotonic()
    temporary_path, request_sha256 = await persist_bounded_upload(file)
    try:
        try:
            reservation = await run_in_threadpool(
                reserve_operation,
                database_url=settings.database_url,
                identifier_hash_key=settings.identifier_hash_key,
                subject=principal.subject,
                idempotency_key=idempotency_key,
                request_sha256=request_sha256,
            )
        except SchemaNotCurrentError as error:
            raise safe_error(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "migration_required",
                "Service is not ready.",
            ) from error
        except psycopg.Error as error:
            raise safe_error(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "database_error",
                "Service is not ready.",
            ) from error

        if not reservation.should_process:
            if reservation.operation.request_sha256 != request_sha256:
                raise safe_error(
                    status.HTTP_409_CONFLICT,
                    "idempotency_key_reused",
                    "The idempotency key was already used for another request.",
                )
            emit_operation(reservation.operation, status_override="idempotent_replay")
            return operation_json_response(reservation.operation)

        result = await run_in_threadpool(import_csv, temporary_path, settings.database_url)
        duration_ms = round((time.monotonic() - started_at) * 1000)
        try:
            operation = await run_in_threadpool(
                complete_operation,
                settings.database_url,
                reservation.operation.operation_id,
                reservation.operation.attempt_count,
                result,
                duration_ms,
            )
        except (psycopg.Error, SchemaNotCurrentError) as error:
            raise safe_error(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "database_error",
                "Service is not ready.",
            ) from error
        emit_operation(operation)
        return operation_json_response(operation)
    finally:
        temporary_path.unlink(missing_ok=True)


@app.get(
    "/v1/imports/{operation_id}",
    response_model=OperationResponse,
    responses={401: {}, 404: {}, 503: {}},
    tags=["imports"],
)
async def read_import(
    operation_id: uuid.UUID,
    principal: Annotated[Principal, Depends(authenticate)],
    settings: Annotated[Settings, Depends(api_settings)],
) -> OperationResponse:
    try:
        operation = await run_in_threadpool(get_operation, settings.database_url, operation_id)
    except (psycopg.Error, SchemaNotCurrentError) as error:
        raise safe_error(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "database_error",
            "Service is not ready.",
        ) from error
    if operation is None:
        raise safe_error(status.HTTP_404_NOT_FOUND, "not_found", "Operation was not found.")
    actor_hash = protected_hash(settings.identifier_hash_key, "actor", principal.subject)
    if "auditor" not in principal.roles and operation.actor_hash != actor_hash:
        raise safe_error(status.HTTP_404_NOT_FOUND, "not_found", "Operation was not found.")
    return public_operation(operation)


@app.get(
    "/v1/integrations/{operation_id}",
    response_model=IntegrationResponse,
    responses={401: {}, 404: {}, 503: {}},
    tags=["integrations"],
)
async def read_integration(
    operation_id: uuid.UUID,
    principal: Annotated[Principal, Depends(authenticate)],
    settings: Annotated[Settings, Depends(api_settings)],
) -> IntegrationResponse:
    try:
        operation = await run_in_threadpool(get_operation, settings.database_url, operation_id)
        event = await run_in_threadpool(
            get_event_for_operation, settings.database_url, operation_id
        )
    except (psycopg.Error, SchemaNotCurrentError) as error:
        raise safe_error(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "database_error",
            "Service is not ready.",
        ) from error
    if operation is None or event is None:
        raise safe_error(status.HTTP_404_NOT_FOUND, "not_found", "Integration was not found.")
    actor_hash = protected_hash(settings.identifier_hash_key, "actor", principal.subject)
    if "auditor" not in principal.roles and operation.actor_hash != actor_hash:
        raise safe_error(status.HTTP_404_NOT_FOUND, "not_found", "Integration was not found.")
    return public_integration(event)


def run() -> None:
    try:
        settings = Settings.from_environment()
    except ConfigurationError as error:
        raise SystemExit("API configuration is incomplete.") from error
    uvicorn.run(
        app,
        host=settings.api_host,
        port=settings.api_port,
        access_log=False,
        log_config=None,
    )
