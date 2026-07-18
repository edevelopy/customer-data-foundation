from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace

import jwt
import pytest
from fastapi.testclient import TestClient

from fde_foundation.ai import (
    AIProviderUnavailableError,
    AIRefusalError,
    AITrace,
    QueryPlan,
    QueryPlanResult,
    TokenUsage,
    estimate_cost_usd,
)
from fde_foundation.api import app, query_planner
from fde_foundation.openai_provider import OpenAIQueryPlanner
from fde_foundation.settings import AISettings, ConfigurationError

JWT_SECRET = "test-jwt-signing-key-with-more-than-thirty-two-characters"


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


def plan() -> QueryPlan:
    return QueryPlan(
        normalized_question="Cual es la politica de reembolso?",
        language="es",
        intent="policy",
        requires_retrieval=True,
        sensitive_action=False,
        risk_flags=["none"],
    )


def parsed_response(*, content_type: str = "output_text") -> SimpleNamespace:
    if content_type == "refusal":
        content = SimpleNamespace(type="refusal", refusal="not available")
    else:
        content = SimpleNamespace(type="output_text", parsed=plan())
    return SimpleNamespace(
        id="resp_test",
        model="gpt-test-2026-07-01",
        output=[SimpleNamespace(type="message", content=[content])],
        usage=SimpleNamespace(
            input_tokens=100,
            output_tokens=50,
            total_tokens=150,
            input_tokens_details=SimpleNamespace(cached_tokens=25),
            output_tokens_details=SimpleNamespace(reasoning_tokens=10),
        ),
    )


class FakeResponses:
    def __init__(self, response: SimpleNamespace) -> None:
        self.response = response
        self.kwargs: dict[str, object] = {}

    def parse(self, **kwargs: object) -> SimpleNamespace:
        self.kwargs = kwargs
        return self.response


class FakeOpenAIClient:
    def __init__(self, response: SimpleNamespace) -> None:
        self.responses = FakeResponses(response)


def test_openai_adapter_uses_responses_structured_output_without_storage() -> None:
    client = FakeOpenAIClient(parsed_response())
    result = OpenAIQueryPlanner(ai_settings(), client=client).plan(
        "Cual es la politica de reembolso?", request_id="request-1"
    )

    assert result.plan.intent == "policy"
    assert result.trace.request_id == "request-1"
    assert result.trace.provider_response_id == "resp_test"
    assert result.trace.usage.cached_input_tokens == 25
    assert result.trace.usage.reasoning_tokens == 10
    assert result.trace.estimated_cost_usd == Decimal("0.00060000")
    assert client.responses.kwargs["store"] is False
    assert client.responses.kwargs["text_format"] is QueryPlan
    assert client.responses.kwargs["model"] == "gpt-test"
    assert client.responses.kwargs["input"] == "Cual es la politica de reembolso?"
    assert "untrusted data" in str(client.responses.kwargs["instructions"])


def test_openai_adapter_detects_refusal_and_unparseable_output() -> None:
    refusal_client = FakeOpenAIClient(parsed_response(content_type="refusal"))
    with pytest.raises(AIRefusalError):
        OpenAIQueryPlanner(ai_settings(), client=refusal_client).plan("question", request_id="r1")

    missing = parsed_response()
    missing.output[0].content[0].parsed = None
    with pytest.raises(AIProviderUnavailableError):
        OpenAIQueryPlanner(ai_settings(), client=FakeOpenAIClient(missing)).plan(
            "question", request_id="r2"
        )


def test_cost_is_unknown_until_current_pricing_is_configured() -> None:
    usage = TokenUsage(
        input_tokens=100,
        output_tokens=50,
        total_tokens=150,
        cached_input_tokens=0,
        reasoning_tokens=0,
    )

    assert (
        estimate_cost_usd(
            usage,
            input_cost_per_million_usd=None,
            output_cost_per_million_usd=Decimal("8"),
        )
        is None
    )


def test_ai_settings_support_key_file_and_reject_invalid_limits(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    key_file = tmp_path / "openai-key"
    key_file.write_text("sk-managed-key-with-more-than-twenty-characters\n", encoding="utf-8")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY_FILE", str(key_file))
    monkeypatch.setenv("OPENAI_MODEL", "gpt-test")
    monkeypatch.setenv("OPENAI_INPUT_COST_PER_MILLION_USD", "2.5")
    monkeypatch.setenv("OPENAI_OUTPUT_COST_PER_MILLION_USD", "10")

    settings = AISettings.from_environment()

    assert settings.api_key.startswith("sk-managed")
    assert settings.input_cost_per_million_usd == Decimal("2.5")
    monkeypatch.setenv("OPENAI_MAX_RETRIES", "20")
    with pytest.raises(ConfigurationError):
        AISettings.from_environment()


class StubPlanner:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error

    def plan(self, _question: str, *, request_id: str) -> QueryPlanResult:
        if self.error is not None:
            raise self.error
        return QueryPlanResult(
            plan=plan(),
            trace=AITrace(
                request_id=request_id,
                provider_response_id="resp_stub",
                model="gpt-test",
                duration_ms=5,
                usage=TokenUsage(
                    input_tokens=10,
                    output_tokens=5,
                    total_tokens=15,
                    cached_input_tokens=0,
                    reasoning_tokens=0,
                ),
                estimated_cost_usd=None,
            ),
        )


def bearer_token() -> str:
    return jwt.encode(
        {
            "sub": "operator-1",
            "roles": ["operator"],
            "iss": "fde-test",
            "aud": "fde-test-audience",
            "exp": 4_102_444_800,
        },
        JWT_SECRET,
        algorithm="HS256",
    )


@pytest.fixture
def api_client(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://not-used")
    monkeypatch.setenv("JWT_SECRET", JWT_SECRET)
    monkeypatch.setenv("IDENTIFIER_HASH_KEY", "identifier-key-with-more-than-thirty-two-characters")
    monkeypatch.setenv("METRICS_TOKEN", "metrics-token-with-more-than-thirty-two-characters")
    monkeypatch.setenv("JWT_ISSUER", "fde-test")
    monkeypatch.setenv("JWT_AUDIENCE", "fde-test-audience")
    app.dependency_overrides[query_planner] = lambda: StubPlanner()
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def test_query_plan_endpoint_is_authenticated_structured_and_safe(api_client: TestClient) -> None:
    anonymous = api_client.post(
        "/v1/assistant/query-plans", json={"question": "Cual es la politica?"}
    )
    response = api_client.post(
        "/v1/assistant/query-plans",
        headers={"Authorization": f"Bearer {bearer_token()}"},
        json={"question": "Cual es la politica?"},
    )

    assert anonymous.status_code == 401
    assert response.status_code == 200
    assert response.json()["plan"]["intent"] == "policy"
    assert response.json()["trace"]["provider_storage_enabled"] is False
    assert "Cual es la politica?" not in response.json()["trace"].values()


@pytest.mark.parametrize(
    ("error", "expected_status", "expected_code"),
    [
        (AIRefusalError(), 422, "ai_refused"),
        (AIProviderUnavailableError(), 503, "ai_provider_unavailable"),
    ],
)
def test_query_plan_endpoint_maps_provider_failures_to_safe_errors(
    api_client: TestClient,
    error: Exception,
    expected_status: int,
    expected_code: str,
) -> None:
    app.dependency_overrides[query_planner] = lambda: StubPlanner(error)
    response = api_client.post(
        "/v1/assistant/query-plans",
        headers={"Authorization": f"Bearer {bearer_token()}"},
        json={"question": "Cual es la politica?"},
    )

    assert response.status_code == expected_status
    assert response.json()["detail"]["code"] == expected_code


def test_missing_provider_key_fails_closed_after_authentication(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://not-used")
    monkeypatch.setenv("JWT_SECRET", JWT_SECRET)
    monkeypatch.setenv("IDENTIFIER_HASH_KEY", "identifier-key-with-more-than-thirty-two-characters")
    monkeypatch.setenv("METRICS_TOKEN", "metrics-token-with-more-than-thirty-two-characters")
    monkeypatch.setenv("JWT_ISSUER", "fde-test")
    monkeypatch.setenv("JWT_AUDIENCE", "fde-test-audience")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY_FILE", raising=False)
    app.dependency_overrides.clear()

    with TestClient(app) as client:
        anonymous = client.post(
            "/v1/assistant/query-plans", json={"question": "Cual es la politica?"}
        )
        authenticated = client.post(
            "/v1/assistant/query-plans",
            headers={"Authorization": f"Bearer {bearer_token()}"},
            json={"question": "Cual es la politica?"},
        )

    assert anonymous.status_code == 401
    assert authenticated.status_code == 503
    assert authenticated.json()["detail"]["code"] == "ai_not_configured"
