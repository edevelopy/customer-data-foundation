"""Reproducible Phase 4 evaluation over versioned synthetic enterprise knowledge."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from fde_foundation.embeddings import DeterministicEmbeddingProvider
from fde_foundation.knowledge import ingest_document, retrieve_chunks
from fde_foundation.rag import DeterministicGroundedGenerator, answer_question
from fde_foundation.settings import ConfigurationError, read_secret

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DOCUMENTS = PROJECT_ROOT / "examples/knowledge/phase4-documents.json"
DEFAULT_CASES = PROJECT_ROOT / "examples/evals/phase4-cases.jsonl"
EVALUATOR_VERSION = "1.0.0"
EVAL_ACTOR = "phase4-evaluation-owner"


class EvaluationCase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str = Field(min_length=1, max_length=100)
    subject: str = Field(min_length=1, max_length=200)
    question: str = Field(min_length=3, max_length=2000)
    should_answer: bool
    expected_source: str | None
    expected_terms: list[str]


def _load_cases(path: Path) -> list[EvaluationCase]:
    cases = [
        EvaluationCase.model_validate_json(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if len(cases) < 30 or len({case.case_id for case in cases}) != len(cases):
        raise ValueError("Evaluation requires at least 30 uniquely identified cases.")
    return cases


def _load_documents(path: Path) -> tuple[str, list[dict[str, Any]]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("documents"), list):
        raise ValueError("Document manifest is invalid.")
    return str(payload.get("dataset_version", "unknown")), payload["documents"]


def _seed_documents(
    *,
    database_url: str,
    identifier_hash_key: str,
    documents: list[dict[str, Any]],
) -> None:
    provider = DeterministicEmbeddingProvider()
    for document in documents:
        ingest_document(
            database_url=database_url,
            identifier_hash_key=identifier_hash_key,
            actor_subject=EVAL_ACTOR,
            reader_subjects=list(document["readers"]),
            source_uri=str(document["source_uri"]),
            title=str(document["title"]),
            content=str(document["content"]),
            metadata=dict(document["metadata"]),
            embedding_provider=provider,
        )


def _ratio(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 4) if denominator else 0.0


def _percentile_95(values: list[int]) -> int:
    if not values:
        return 0
    ordered = sorted(values)
    return ordered[max(0, (len(ordered) * 95 + 99) // 100 - 1)]


def run_evaluation(
    *,
    database_url: str,
    identifier_hash_key: str,
    documents_path: Path = DEFAULT_DOCUMENTS,
    cases_path: Path = DEFAULT_CASES,
) -> dict[str, Any]:
    dataset_version, documents = _load_documents(documents_path)
    cases = _load_cases(cases_path)
    _seed_documents(
        database_url=database_url,
        identifier_hash_key=identifier_hash_key,
        documents=documents,
    )
    embeddings = DeterministicEmbeddingProvider()
    generator = DeterministicGroundedGenerator()
    results: list[dict[str, Any]] = []
    positive_count = sum(case.should_answer for case in cases)
    negative_count = len(cases) - positive_count
    baseline_found = improved_found = 0
    improved_relevant_hits = improved_total_hits = 0
    correct_answers = grounded_answers = correct_refusals = 0
    permission_leakage_count = 0
    baseline_latencies: list[int] = []
    improved_latencies: list[int] = []
    total_input_tokens = total_output_tokens = 0
    total_cost = 0.0

    for case in cases:
        started = time.monotonic()
        baseline_hits = retrieve_chunks(
            database_url=database_url,
            identifier_hash_key=identifier_hash_key,
            actor_subject=case.subject,
            query=case.question,
            embedding_provider=embeddings,
            mode="lexical",
            limit=1,
        )
        baseline_ms = round((time.monotonic() - started) * 1000)
        started = time.monotonic()
        improved_hits = retrieve_chunks(
            database_url=database_url,
            identifier_hash_key=identifier_hash_key,
            actor_subject=case.subject,
            query=case.question,
            embedding_provider=embeddings,
            mode="hybrid",
            limit=3,
        )
        answer = answer_question(
            database_url=database_url,
            identifier_hash_key=identifier_hash_key,
            actor_subject=case.subject,
            question=case.question,
            metadata_filter={},
            embedding_provider=embeddings,
            answer_generator=generator,
        )
        improved_ms = round((time.monotonic() - started) * 1000)
        baseline_sources = [hit.source_uri for hit in baseline_hits]
        improved_sources = [hit.source_uri for hit in improved_hits]
        citation_sources = [citation.source_uri for citation in answer.citations]
        baseline_case_found = bool(case.should_answer and case.expected_source in baseline_sources)
        improved_case_found = bool(case.should_answer and case.expected_source in improved_sources)
        if baseline_case_found:
            baseline_found += 1
        if improved_case_found:
            improved_found += 1
        if case.should_answer:
            relevant_hits = sum(source == case.expected_source for source in improved_sources)
            improved_relevant_hits += relevant_hits
            improved_total_hits += len(improved_sources)
            terms_present = all(
                term.casefold() in answer.answer.casefold() for term in case.expected_terms
            )
            answer_correct = answer.status == "answered" and terms_present
            grounded = bool(citation_sources) and all(
                source == case.expected_source for source in citation_sources
            )
            correct_answers += answer_correct
            grounded_answers += grounded
            refusal_correct = False
        else:
            answer_correct = False
            grounded = False
            refusal_correct = answer.status == "refused" and not answer.citations
            correct_refusals += refusal_correct
            if case.expected_source is not None and (
                case.expected_source in improved_sources or case.expected_source in citation_sources
            ):
                permission_leakage_count += 1
        baseline_latencies.append(baseline_ms)
        improved_latencies.append(improved_ms)
        total_input_tokens += answer.trace.usage.input_tokens
        total_output_tokens += answer.trace.usage.output_tokens
        total_cost += float(answer.trace.estimated_cost_usd or 0)
        results.append(
            {
                "case_id": case.case_id,
                "should_answer": case.should_answer,
                "baseline_found_expected_source": baseline_case_found,
                "improved_found_expected_source": improved_case_found,
                "answer_status": answer.status,
                "answer_correct": answer_correct,
                "grounded": grounded,
                "refusal_correct": refusal_correct,
                "citation_sources": citation_sources,
                "baseline_latency_ms": baseline_ms,
                "improved_latency_ms": improved_ms,
            }
        )

    metrics = {
        "case_count": len(cases),
        "positive_case_count": positive_count,
        "negative_case_count": negative_count,
        "baseline_retrieval_recall": _ratio(baseline_found, positive_count),
        "improved_retrieval_recall": _ratio(improved_found, positive_count),
        "improved_retrieval_precision": _ratio(improved_relevant_hits, improved_total_hits),
        "answer_accuracy": _ratio(correct_answers, positive_count),
        "groundedness": _ratio(grounded_answers, positive_count),
        "refusal_accuracy": _ratio(correct_refusals, negative_count),
        "permission_leakage_count": permission_leakage_count,
        "baseline_p95_latency_ms": _percentile_95(baseline_latencies),
        "improved_p95_latency_ms": _percentile_95(improved_latencies),
        "input_tokens": total_input_tokens,
        "output_tokens": total_output_tokens,
        "estimated_cost_usd": round(total_cost, 8),
    }
    acceptance = {
        "at_least_30_cases": metrics["case_count"] >= 30,
        "retrieval_not_worse_than_baseline": (
            metrics["improved_retrieval_recall"] >= metrics["baseline_retrieval_recall"]
        ),
        "answer_accuracy_at_least_85_percent": metrics["answer_accuracy"] >= 0.85,
        "groundedness_at_least_95_percent": metrics["groundedness"] >= 0.95,
        "refusal_accuracy_at_least_95_percent": metrics["refusal_accuracy"] >= 0.95,
        "zero_permission_leakage": metrics["permission_leakage_count"] == 0,
    }
    return {
        "schema_version": "1.0.0",
        "evaluator_version": EVALUATOR_VERSION,
        "dataset_version": dataset_version,
        "generated_at": datetime.now(UTC).isoformat(),
        "provider": "deterministic_local",
        "provider_is_ai": False,
        "documents_sha256": hashlib.sha256(documents_path.read_bytes()).hexdigest(),
        "cases_sha256": hashlib.sha256(cases_path.read_bytes()).hexdigest(),
        "metrics": metrics,
        "acceptance": acceptance,
        "passed": all(acceptance.values()),
        "cases": results,
        "limitations": [
            "The deterministic provider validates reproducibility and controls, "
            "not OpenAI quality.",
            "Live model token usage, cost, and answer quality remain unmeasured "
            "without a credential.",
            "Synthetic documents must be replaced or complemented with approved client cases.",
        ],
    }


def render_markdown(report: dict[str, Any]) -> str:
    metrics = report["metrics"]
    acceptance = report["acceptance"]
    lines = [
        "# Resultados reproducibles — Fase 4",
        "",
        f"Generado: {report['generated_at']}.",
        "",
        f"Resultado: **{'APROBADO' if report['passed'] else 'NO APROBADO'}**.",
        "",
        "## Metricas",
        "",
        "| Metrica | Resultado |",
        "|---|---:|",
    ]
    for name, value in metrics.items():
        lines.append(f"| `{name}` | {value} |")
    lines.extend(["", "## Puertas de aceptacion", ""])
    for name, passed in acceptance.items():
        lines.append(f"- {'PASS' if passed else 'FAIL'} — `{name}`")
    lines.extend(
        [
            "",
            "## Integridad",
            "",
            f"- Dataset: `{report['dataset_version']}`.",
            f"- SHA-256 documentos: `{report['documents_sha256']}`.",
            f"- SHA-256 casos: `{report['cases_sha256']}`.",
            "- Proveedor: `deterministic_local` (no es IA).",
            "",
            "## Limites",
            "",
        ]
    )
    lines.extend(f"- {limitation}" for limitation in report["limitations"])
    lines.extend(
        [
            "",
            "## Que sigue",
            "",
            "Incremento 5: tool calling controlado, aprobacion humana, auditoria, limites de uso, "
            "cache y degradacion segura.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the versioned Phase 4 RAG evaluation.")
    parser.add_argument("--documents", type=Path, default=DEFAULT_DOCUMENTS)
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--json-output", type=Path)
    parser.add_argument("--markdown-output", type=Path)
    args = parser.parse_args()
    try:
        database_url = read_secret("DATABASE_URL", minimum_length=1)
        identifier_hash_key = read_secret("IDENTIFIER_HASH_KEY")
    except ConfigurationError as error:
        raise SystemExit("Evaluation configuration is incomplete.") from error
    if os.environ.get("APP_ENV", "production") not in {"development", "test"}:
        raise SystemExit("Evaluation seeding is allowed only in development or test.")
    report = run_evaluation(
        database_url=database_url,
        identifier_hash_key=identifier_hash_key,
        documents_path=args.documents,
        cases_path=args.cases,
    )
    serialized = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.json_output:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(serialized, encoding="utf-8")
    if args.markdown_output:
        args.markdown_output.parent.mkdir(parents=True, exist_ok=True)
        args.markdown_output.write_text(render_markdown(report), encoding="utf-8")
    print(serialized, end="")
    raise SystemExit(0 if report["passed"] else 1)
