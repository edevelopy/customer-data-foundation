"""Cliente HTTP sintetico para verificar el stack Docker desde otro contenedor."""

from __future__ import annotations

import json
import os
import uuid
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

CSV_CONTENT = (
    b"email,first_name,last_name,phone,source\n"
    b"container.smoke@example.com,Container,Smoke,+14075550198,synthetic\n"
)


def fetch_json(request: Request) -> tuple[int, dict[str, object]]:
    try:
        with urlopen(request, timeout=10) as response:
            return response.status, json.loads(response.read())
    except HTTPError as error:
        raise RuntimeError(f"container smoke request returned HTTP {error.code}") from None
    except (URLError, TimeoutError, json.JSONDecodeError) as error:
        raise RuntimeError("container smoke request failed") from error


def main() -> int:
    token = os.environ.get("OPERATOR_TOKEN", "")
    base_url = os.environ.get("API_BASE_URL", "http://api:8000")
    if not token:
        raise SystemExit("OPERATOR_TOKEN is required")

    ready_status, ready = fetch_json(Request(f"{base_url}/health/ready"))
    if ready_status != 200 or ready != {"status": "ready"}:
        raise RuntimeError("containerized API is not ready")

    boundary = f"fde-smoke-{uuid.uuid4().hex}"
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
            "Idempotency-Key": "container-smoke-import-0001",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
        method="POST",
    )
    response_status, payload = fetch_json(request)
    serialized = json.dumps(payload)
    if response_status != 200 or payload.get("status") not in {"imported", "already_imported"}:
        raise RuntimeError("containerized import did not complete")
    if "container.smoke@example.com" in serialized:
        raise RuntimeError("containerized response exposed input data")

    print(
        json.dumps(
            {
                "accepted": payload.get("accepted"),
                "attempt_count": payload.get("attempt_count"),
                "inserted_rows": payload.get("inserted_rows"),
                "operation_id": payload.get("operation_id"),
                "status": payload.get("status"),
            },
            separators=(",", ":"),
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
