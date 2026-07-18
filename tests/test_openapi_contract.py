from __future__ import annotations

import json
from pathlib import Path

from fde_foundation.api import app

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_versioned_openapi_matches_runtime_contract() -> None:
    exported = json.loads((PROJECT_ROOT / "docs" / "openapi.json").read_text(encoding="utf-8"))
    runtime = app.openapi()

    assert exported == runtime
    assert exported["openapi"] == "3.1.0"
    assert set(exported["paths"]) == {
        "/health/live",
        "/health/ready",
        "/v1/assistant/query-plans",
        "/v1/imports",
        "/v1/imports/{operation_id}",
        "/v1/integrations/{operation_id}",
        "/v1/knowledge/documents",
        "/v1/knowledge/retrieval",
    }
    assert exported["components"]["securitySchemes"]["BearerAuth"] == {
        "type": "http",
        "scheme": "bearer",
    }
