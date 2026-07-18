from __future__ import annotations

import os

import psycopg
import pytest

from fde_foundation.database import upgrade_database
from fde_foundation.evaluation import render_markdown, run_evaluation

DATABASE_URL = "postgresql://fde_test:test-only-password@localhost:55435/fde_test"
HASH_KEY = "test-evaluation-hash-key-with-more-than-thirty-two-characters"


@pytest.fixture
def database_url() -> str:
    url = os.environ.get(
        "PHASE4_TEST_DATABASE_URL", os.environ.get("TEST_DATABASE_URL", DATABASE_URL)
    )
    upgrade_database(url)
    with psycopg.connect(url) as connection:
        connection.execute(
            "TRUNCATE rag_cache, rag_traces, knowledge_chunks, "
            "knowledge_document_permissions, knowledge_documents CASCADE"
        )
    return url


@pytest.mark.integration
def test_phase4_evaluation_has_30_cases_and_passes_versioned_gates(database_url: str) -> None:
    report = run_evaluation(database_url=database_url, identifier_hash_key=HASH_KEY)

    assert report["metrics"]["case_count"] >= 30
    assert report["metrics"]["permission_leakage_count"] == 0
    assert report["acceptance"]["retrieval_not_worse_than_baseline"] is True
    assert report["passed"] is True
    assert report["provider_is_ai"] is False
    assert len(report["documents_sha256"]) == 64
    assert len(report["cases_sha256"]) == 64
    assert all("question" not in result for result in report["cases"])
    assert "APROBADO" in render_markdown(report)


@pytest.mark.integration
def test_phase4_quality_metrics_are_reproducible_on_replay(database_url: str) -> None:
    first = run_evaluation(database_url=database_url, identifier_hash_key=HASH_KEY)
    second = run_evaluation(database_url=database_url, identifier_hash_key=HASH_KEY)
    quality_metrics = {
        "case_count",
        "baseline_retrieval_recall",
        "improved_retrieval_recall",
        "improved_retrieval_precision",
        "answer_accuracy",
        "groundedness",
        "refusal_accuracy",
        "permission_leakage_count",
        "input_tokens",
        "output_tokens",
        "estimated_cost_usd",
    }

    assert {key: first["metrics"][key] for key in quality_metrics} == {
        key: second["metrics"][key] for key in quality_metrics
    }
    assert first["acceptance"] == second["acceptance"]
