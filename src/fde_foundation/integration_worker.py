"""Worker de entrega at-least-once con firma, timeout, backoff y dead letter."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import signal
import time
from dataclasses import dataclass
from pathlib import Path
from threading import Event
from typing import Final
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from fde_foundation.integration_store import (
    OutboxEvent,
    claim_next_event,
    mark_delivered,
    mark_failed_attempt,
)
from fde_foundation.observability import emit_json_event
from fde_foundation.settings import ConfigurationError

SIGNATURE_VERSION: Final = "v1"


@dataclass(frozen=True)
class WorkerSettings:
    database_url: str
    partner_url: str
    webhook_secret: str
    timeout_seconds: float
    max_attempts: int
    base_backoff_seconds: int
    max_backoff_seconds: int
    lease_seconds: int
    poll_seconds: float

    @classmethod
    def from_environment(cls) -> WorkerSettings:
        database_url = os.environ.get("INTEGRATION_DATABASE_URL") or os.environ.get(
            "DATABASE_URL", ""
        )
        partner_url = os.environ.get("PARTNER_WEBHOOK_URL", "")
        webhook_secret = os.environ.get("PARTNER_WEBHOOK_SECRET", "")
        try:
            timeout_seconds = int(os.environ.get("INTEGRATION_TIMEOUT_MS", "2000")) / 1000
            max_attempts = int(os.environ.get("INTEGRATION_MAX_ATTEMPTS", "5"))
            base_backoff_seconds = int(os.environ.get("INTEGRATION_BASE_BACKOFF_SECONDS", "2"))
            max_backoff_seconds = int(os.environ.get("INTEGRATION_MAX_BACKOFF_SECONDS", "60"))
            lease_seconds = int(os.environ.get("INTEGRATION_LEASE_SECONDS", "30"))
            poll_seconds = float(os.environ.get("INTEGRATION_POLL_SECONDS", "0.5"))
        except ValueError as error:
            raise ConfigurationError from error
        if not database_url or not partner_url.startswith(("http://", "https://")):
            raise ConfigurationError
        if len(webhook_secret) < 32:
            raise ConfigurationError
        if not 0.1 <= timeout_seconds <= 30:
            raise ConfigurationError
        if not 1 <= max_attempts <= 20:
            raise ConfigurationError
        if not 1 <= base_backoff_seconds <= max_backoff_seconds <= 3600:
            raise ConfigurationError
        if lease_seconds <= timeout_seconds or not 0.05 <= poll_seconds <= 60:
            raise ConfigurationError
        return cls(
            database_url=database_url,
            partner_url=partner_url,
            webhook_secret=webhook_secret,
            timeout_seconds=timeout_seconds,
            max_attempts=max_attempts,
            base_backoff_seconds=base_backoff_seconds,
            max_backoff_seconds=max_backoff_seconds,
            lease_seconds=lease_seconds,
            poll_seconds=poll_seconds,
        )


@dataclass(frozen=True)
class DeliveryResult:
    delivered: bool
    retryable: bool
    error_code: str | None
    duration_ms: int


def canonical_body(payload: dict[str, object]) -> bytes:
    return json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()


def signature(secret: str, timestamp: str, body: bytes) -> str:
    signed = timestamp.encode() + b"." + body
    digest = hmac.new(secret.encode(), signed, hashlib.sha256).hexdigest()
    return f"{SIGNATURE_VERSION}={digest}"


def classify_http_status(status_code: int) -> tuple[bool, str]:
    if status_code in {408, 425, 429} or status_code >= 500:
        return True, f"partner_http_{status_code}"
    return False, f"partner_http_{status_code}"


def deliver_event(event: OutboxEvent, settings: WorkerSettings) -> DeliveryResult:
    started_at = time.monotonic()
    body = canonical_body(event.payload)
    timestamp = str(int(time.time()))
    request = Request(
        settings.partner_url,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Idempotency-Key": str(event.event_id),
            "X-FDE-Event-Id": str(event.event_id),
            "X-FDE-Signature": signature(settings.webhook_secret, timestamp, body),
            "X-FDE-Timestamp": timestamp,
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=settings.timeout_seconds) as response:
            delivered = 200 <= response.status < 300
            if delivered:
                return DeliveryResult(True, False, None, elapsed_ms(started_at))
            retryable, code = classify_http_status(response.status)
            return DeliveryResult(False, retryable, code, elapsed_ms(started_at))
    except HTTPError as error:
        retryable, code = classify_http_status(error.code)
        return DeliveryResult(False, retryable, code, elapsed_ms(started_at))
    except TimeoutError:
        return DeliveryResult(False, True, "partner_timeout", elapsed_ms(started_at))
    except URLError as error:
        code = (
            "partner_timeout" if isinstance(error.reason, TimeoutError) else "partner_unreachable"
        )
        return DeliveryResult(False, True, code, elapsed_ms(started_at))


def elapsed_ms(started_at: float) -> int:
    return round((time.monotonic() - started_at) * 1000)


def emit_delivery_event(event: OutboxEvent, result_status: str, result: DeliveryResult) -> None:
    emit_json_event(
        {
            "attempt_count": event.attempt_count,
            "duration_ms": result.duration_ms,
            "error_code": result.error_code,
            "event_id": str(event.event_id),
            "event_type": event.event_type,
            "status": result_status,
        }
    )


def process_one(settings: WorkerSettings) -> bool:
    event = claim_next_event(settings.database_url, lease_seconds=settings.lease_seconds)
    if event is None:
        return False
    result = deliver_event(event, settings)
    if result.delivered:
        persisted = mark_delivered(settings.database_url, event)
        final_status = "delivered" if persisted else "stale_attempt"
    else:
        final_status = mark_failed_attempt(
            settings.database_url,
            event,
            error_code=result.error_code or "partner_unknown_error",
            retryable=result.retryable,
            max_attempts=settings.max_attempts,
            base_backoff_seconds=settings.base_backoff_seconds,
            max_backoff_seconds=settings.max_backoff_seconds,
        )
    emit_delivery_event(event, final_status, result)
    return True


def run() -> None:
    try:
        settings = WorkerSettings.from_environment()
    except ConfigurationError as error:
        raise SystemExit("Integration worker configuration is incomplete.") from error

    Path("/tmp/fde-integration-worker-ready").touch()
    stopped = Event()

    def stop(_signum: int, _frame: object) -> None:
        stopped.set()

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    while not stopped.is_set():
        processed = process_one(settings)
        if not processed:
            stopped.wait(settings.poll_seconds)


if __name__ == "__main__":
    run()
