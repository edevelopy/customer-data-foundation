"""Prueba externa del flujo importacion -> outbox -> partner con un fallo transitorio."""

from __future__ import annotations

import json
import os
import time
import uuid
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

CSV_CONTENT = (
    b"email,first_name,last_name,phone,source\n"
    b"integration.smoke@example.com,Integration,Smoke,+14075550197,synthetic\n"
)


def fetch_json(request: Request) -> tuple[int, dict[str, object]]:
    try:
        with urlopen(request, timeout=10) as response:
            return response.status, json.loads(response.read())
    except HTTPError as error:
        raise RuntimeError(f"integration smoke request returned HTTP {error.code}") from None
    except (URLError, TimeoutError, json.JSONDecodeError) as error:
        raise RuntimeError("integration smoke request failed") from error


def main() -> int:
    token = os.environ.get("OPERATOR_TOKEN", "")
    base_url = os.environ.get("API_BASE_URL", "http://api:8000")
    if not token:
        raise SystemExit("OPERATOR_TOKEN is required")

    boundary = f"fde-integration-{uuid.uuid4().hex}"
    body = (
        (
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="file"; filename="synthetic.csv"\r\n'
            "Content-Type: text/csv\r\n\r\n"
        ).encode()
        + CSV_CONTENT
        + f"\r\n--{boundary}--\r\n".encode()
    )
    request = Request(
        f"{base_url}/v1/imports",
        data=body,
        headers={
            "Authorization": f"Bearer {token}",
            "Idempotency-Key": f"integration-smoke-{uuid.uuid4()}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
        method="POST",
    )
    response_status, payload = fetch_json(request)
    if response_status != 200 or payload.get("status") not in {"imported", "already_imported"}:
        raise RuntimeError("integration smoke import did not complete")
    operation_id = payload.get("operation_id")

    final: dict[str, object] | None = None
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        status_request = Request(
            f"{base_url}/v1/integrations/{operation_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        _, current = fetch_json(status_request)
        if current.get("status") in {"delivered", "dead_letter"}:
            final = current
            break
        time.sleep(0.25)

    if final is None or final.get("status") != "delivered":
        raise RuntimeError("partner event was not delivered")
    attempt_count = final.get("attempt_count")
    if not isinstance(attempt_count, int) or attempt_count < 2:
        raise RuntimeError("transient failure was not retried")
    serialized = json.dumps(final)
    if "integration.smoke@example.com" in serialized or "+14075550197" in serialized:
        raise RuntimeError("integration status exposed customer data")

    print(
        json.dumps(
            {
                "attempt_count": attempt_count,
                "event_id": final.get("event_id"),
                "last_failure_code": final.get("last_failure_code"),
                "operation_id": operation_id,
                "status": final.get("status"),
            },
            separators=(",", ":"),
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
