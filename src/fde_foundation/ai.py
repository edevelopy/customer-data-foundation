"""Contrato estable para planificar consultas antes de recuperar documentos."""

from __future__ import annotations

from decimal import Decimal
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field

PROMPT_ID = "enterprise_query_planner"
PROMPT_VERSION = "1.0.0"


class AIProviderUnavailableError(Exception):
    """El proveedor no produjo una respuesta utilizable."""


class AIRefusalError(Exception):
    """El modelo rechazo procesar la solicitud."""


class QueryPlan(BaseModel):
    """Salida estricta que alimentara la recuperacion RAG en el siguiente incremento."""

    model_config = ConfigDict(extra="forbid")

    normalized_question: str = Field(min_length=1, max_length=2000)
    language: Literal["es", "en", "other"]
    intent: Literal["policy", "procedure", "customer_data", "general"]
    requires_retrieval: bool
    sensitive_action: bool
    risk_flags: list[
        Literal[
            "none",
            "prompt_injection",
            "personal_data",
            "credential_request",
            "sensitive_action",
        ]
    ] = Field(min_length=1, max_length=5)


class TokenUsage(BaseModel):
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    total_tokens: int = Field(ge=0)
    cached_input_tokens: int = Field(ge=0)
    reasoning_tokens: int = Field(ge=0)


class AITrace(BaseModel):
    request_id: str
    provider_response_id: str
    provider: Literal["openai"] = "openai"
    model: str
    prompt_id: str = PROMPT_ID
    prompt_version: str = PROMPT_VERSION
    duration_ms: int = Field(ge=0)
    usage: TokenUsage
    estimated_cost_usd: Decimal | None
    provider_storage_enabled: bool = False


class QueryPlanResult(BaseModel):
    plan: QueryPlan
    trace: AITrace


class QueryPlanner(Protocol):
    def plan(self, question: str, *, request_id: str) -> QueryPlanResult: ...


def estimate_cost_usd(
    usage: TokenUsage,
    *,
    input_cost_per_million_usd: Decimal | None,
    output_cost_per_million_usd: Decimal | None,
) -> Decimal | None:
    if input_cost_per_million_usd is None or output_cost_per_million_usd is None:
        return None
    million = Decimal(1_000_000)
    cost = (
        Decimal(usage.input_tokens) * input_cost_per_million_usd
        + Decimal(usage.output_tokens) * output_cost_per_million_usd
    ) / million
    return cost.quantize(Decimal("0.00000001"))
