"""Eventos operativos estructurados y libres de datos personales."""

from __future__ import annotations

import json
import sys
from collections.abc import Iterable
from typing import TextIO


def build_import_event(
    *,
    operation_id: str,
    status: str,
    duration_ms: int,
    total_rows: int,
    inserted_rows: int,
    existing_rows: int,
    error_codes: Iterable[str],
) -> dict[str, object]:
    """Construye exclusivamente el contrato de observabilidad aprobado."""
    return {
        "operation_id": operation_id,
        "status": status,
        "duration_ms": duration_ms,
        "total_rows": total_rows,
        "inserted_rows": inserted_rows,
        "existing_rows": existing_rows,
        "error_codes": sorted(set(error_codes)),
    }


def build_ai_event(
    *,
    request_id: str,
    status: str,
    model: str | None = None,
    prompt_id: str | None = None,
    prompt_version: str | None = None,
    duration_ms: int | None = None,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    estimated_cost_usd: str | None = None,
) -> dict[str, object]:
    """Registra ejecucion y costo sin conservar la pregunta ni la respuesta."""
    return {
        "event_type": "ai_query_plan",
        "request_id": request_id,
        "status": status,
        "model": model,
        "prompt_id": prompt_id,
        "prompt_version": prompt_version,
        "duration_ms": duration_ms,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "estimated_cost_usd": estimated_cost_usd,
    }


def emit_json_event(event: dict[str, object], stream: TextIO | None = None) -> None:
    """Emite exactamente un objeto JSON por linea."""
    destination = stream or sys.stdout
    destination.write(json.dumps(event, separators=(",", ":"), sort_keys=True) + "\n")
    destination.flush()
