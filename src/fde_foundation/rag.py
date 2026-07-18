"""Permission-scoped RAG orchestration with verifiable citations and safe refusal."""

from __future__ import annotations

import json
import re
import time
import uuid
from dataclasses import dataclass
from decimal import Decimal
from typing import Literal, Protocol

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from pydantic import BaseModel, ConfigDict, Field

from fde_foundation.ai import AIProviderUnavailableError, AIRefusalError, TokenUsage
from fde_foundation.api_store import protected_hash
from fde_foundation.database import require_current_schema
from fde_foundation.embeddings import EmbeddingProvider
from fde_foundation.knowledge import (
    INJECTION_PATTERN,
    LEXICAL_STOPWORDS,
    RetrievalHit,
    retrieve_chunks,
)

RAG_PROMPT_ID = "grounded_enterprise_answer"
RAG_PROMPT_VERSION = "1.0.0"
MIN_SEMANTIC_SIMILARITY = 0.35
SAFE_REFUSAL = "No encontre evidencia autorizada suficiente para responder esa pregunta."


class AIRequestLimitError(Exception):
    pass


class AIDailyBudgetError(Exception):
    pass


class GroundedDraft(BaseModel):
    """Strict provider output; cited IDs are validated again by the orchestrator."""

    model_config = ConfigDict(extra="forbid")

    answer: str = Field(min_length=1, max_length=3000)
    supported: bool
    cited_chunk_ids: list[str] = Field(max_length=8)


@dataclass(frozen=True)
class GeneratedAnswer:
    draft: GroundedDraft
    provider: str
    model: str
    provider_response_id: str
    duration_ms: int
    usage: TokenUsage
    estimated_cost_usd: Decimal | None


class AnswerGenerator(Protocol):
    def generate(
        self, question: str, evidence: list[RetrievalHit], *, request_id: str
    ) -> GeneratedAnswer: ...


class Citation(BaseModel):
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    source_uri: str
    title: str
    chunk_index: int


class RAGTrace(BaseModel):
    request_id: uuid.UUID
    status: Literal["answered", "refused", "degraded", "provider_unavailable"]
    provider: str
    model: str
    prompt_version: str = RAG_PROMPT_VERSION
    duration_ms: int = Field(ge=0)
    usage: TokenUsage
    estimated_cost_usd: Decimal | None
    retrieved_count: int = Field(ge=0)
    citation_count: int = Field(ge=0)
    cached: bool = False


class AnswerResult(BaseModel):
    status: Literal["answered", "refused", "degraded"]
    answer: str
    citations: list[Citation]
    trace: RAGTrace


class DeterministicGroundedGenerator:
    """Local extractive test adapter. It is intentionally not presented as AI."""

    name = "deterministic_local"
    model = "extractive-test-v1"

    def generate(
        self, question: str, evidence: list[RetrievalHit], *, request_id: str
    ) -> GeneratedAnswer:
        started_at = time.monotonic()
        hit = evidence[0]
        sentences = re.split(r"(?<=[.!?])\s+", hit.content.strip())
        code_terms = {
            term.casefold()
            for code in re.findall(r"\b[A-Z][A-Z0-9]+-[A-Z0-9-]+\b", question)
            for term in code.split("-")
        }
        question_terms = {
            term
            for term in re.findall(r"[\w]{2,40}", question.casefold(), re.UNICODE)
            if term not in LEXICAL_STOPWORDS and term not in code_terms
        }
        safe_sentences = [
            sentence for sentence in sentences if not INJECTION_PATTERN.search(sentence)
        ]
        ranked = sorted(
            safe_sentences,
            key=lambda candidate: sum(term in candidate.casefold() for term in question_terms),
            reverse=True,
        )
        relevant = [
            sentence
            for sentence in ranked
            if sum(term in sentence.casefold() for term in question_terms) > 0
        ][:2]
        sentence = " ".join(relevant or ranked[:1])
        draft = GroundedDraft(
            answer=sentence[:3000],
            supported=True,
            cited_chunk_ids=[str(hit.chunk_id)],
        )
        usage = TokenUsage(
            input_tokens=0,
            output_tokens=0,
            total_tokens=0,
            cached_input_tokens=0,
            reasoning_tokens=0,
        )
        return GeneratedAnswer(
            draft=draft,
            provider=self.name,
            model=self.model,
            provider_response_id=f"local-{request_id}",
            duration_ms=round((time.monotonic() - started_at) * 1000),
            usage=usage,
            estimated_cost_usd=Decimal("0"),
        )


def evidence_is_sufficient(hit: RetrievalHit) -> bool:
    return bool(
        (hit.lexical_score is not None and hit.lexical_score > 0)
        or (
            hit.semantic_similarity is not None
            and hit.semantic_similarity >= MIN_SEMANTIC_SIMILARITY
        )
    )


def _persist_trace(
    *,
    database_url: str,
    identifier_hash_key: str,
    actor_subject: str,
    question: str,
    trace: RAGTrace,
) -> None:
    principal_hash = protected_hash(identifier_hash_key, "knowledge-principal", actor_subject)
    query_hash = protected_hash(identifier_hash_key, "rag-query", question)
    with psycopg.connect(database_url, row_factory=dict_row) as connection:
        require_current_schema(connection)
        connection.execute(
            """
            INSERT INTO rag_traces (
                request_id, principal_hash, query_hash, status, provider, model,
                prompt_version, duration_ms, input_tokens, output_tokens,
                estimated_cost_usd, retrieved_count, citation_count, cached
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                trace.request_id,
                principal_hash,
                query_hash,
                trace.status,
                trace.provider,
                trace.model,
                trace.prompt_version,
                trace.duration_ms,
                trace.usage.input_tokens,
                trace.usage.output_tokens,
                trace.estimated_cost_usd,
                trace.retrieved_count,
                trace.citation_count,
                trace.cached,
            ),
        )


def _refusal_trace(*, request_id: uuid.UUID, duration_ms: int, retrieved_count: int) -> RAGTrace:
    return RAGTrace(
        request_id=request_id,
        status="refused",
        provider="retrieval_gate",
        model="none",
        duration_ms=duration_ms,
        usage=TokenUsage(
            input_tokens=0,
            output_tokens=0,
            total_tokens=0,
            cached_input_tokens=0,
            reasoning_tokens=0,
        ),
        estimated_cost_usd=Decimal("0"),
        retrieved_count=retrieved_count,
        citation_count=0,
    )


def _principal_hash(identifier_hash_key: str, actor_subject: str) -> str:
    return protected_hash(identifier_hash_key, "knowledge-principal", actor_subject)


def _enforce_request_rate(
    *,
    database_url: str,
    identifier_hash_key: str,
    actor_subject: str,
    requests_per_minute: int,
) -> None:
    if requests_per_minute == 0:
        return
    if not 1 <= requests_per_minute <= 10_000:
        raise ValueError("AI request limit is invalid.")
    with psycopg.connect(database_url, row_factory=dict_row) as connection:
        require_current_schema(connection)
        row = connection.execute(
            """
            SELECT count(*) AS total FROM rag_traces
            WHERE principal_hash = %s AND created_at >= now() - interval '1 minute'
            """,
            (_principal_hash(identifier_hash_key, actor_subject),),
        ).fetchone()
    if row and int(row["total"]) >= requests_per_minute:
        raise AIRequestLimitError


def _enforce_daily_budget(
    *,
    database_url: str,
    identifier_hash_key: str,
    actor_subject: str,
    daily_token_budget: int,
) -> None:
    if daily_token_budget == 0:
        return
    if not 1 <= daily_token_budget <= 1_000_000_000:
        raise ValueError("AI daily token budget is invalid.")
    with psycopg.connect(database_url, row_factory=dict_row) as connection:
        require_current_schema(connection)
        row = connection.execute(
            """
            SELECT coalesce(sum(input_tokens + output_tokens), 0) AS total
            FROM rag_traces
            WHERE principal_hash = %s AND created_at >= date_trunc('day', now())
            """,
            (_principal_hash(identifier_hash_key, actor_subject),),
        ).fetchone()
    if row and int(row["total"]) >= daily_token_budget:
        raise AIDailyBudgetError


def _cache_key(
    *,
    identifier_hash_key: str,
    question: str,
    metadata_filter: dict[str, str],
    embedding_provider: EmbeddingProvider,
    answer_generator: AnswerGenerator,
) -> str:
    payload = json.dumps(
        {
            "question": question,
            "metadata_filter": metadata_filter,
            "prompt_version": RAG_PROMPT_VERSION,
            "embedding_provider": embedding_provider.name,
            "embedding_model": embedding_provider.model,
            "answer_provider": getattr(answer_generator, "name", "openai"),
            "answer_model": getattr(answer_generator, "model", "configured"),
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return protected_hash(identifier_hash_key, "rag-cache-key", payload)


def _cached_answer(
    *,
    database_url: str,
    identifier_hash_key: str,
    actor_subject: str,
    cache_key_hash: str,
    request_id: uuid.UUID,
    question: str,
) -> AnswerResult | None:
    principal_hash = _principal_hash(identifier_hash_key, actor_subject)
    with psycopg.connect(database_url, row_factory=dict_row) as connection:
        require_current_schema(connection)
        row = connection.execute(
            """
            SELECT response FROM rag_cache
            WHERE principal_hash = %s AND cache_key_hash = %s AND expires_at > now()
            """,
            (principal_hash, cache_key_hash),
        ).fetchone()
        if row is None:
            return None
        payload = dict(row["response"])
        citations = [Citation.model_validate(item) for item in payload.get("citations", [])]
        if citations:
            authorized = connection.execute(
                """
                SELECT count(*) AS total
                FROM knowledge_chunks c
                JOIN knowledge_documents d ON d.document_id = c.document_id AND d.active
                JOIN knowledge_document_permissions p ON p.document_id = d.document_id
                WHERE p.principal_hash = %s AND c.chunk_id = ANY(%s)
                """,
                (principal_hash, [citation.chunk_id for citation in citations]),
            ).fetchone()
            if authorized is None or int(authorized["total"]) != len(citations):
                return None
    status = payload.get("status")
    if status not in {"answered", "refused", "degraded"}:
        return None
    trace = RAGTrace(
        request_id=request_id,
        status=status,
        provider="cache",
        model=str(payload.get("model", "cached")),
        duration_ms=0,
        usage=TokenUsage(
            input_tokens=0,
            output_tokens=0,
            total_tokens=0,
            cached_input_tokens=0,
            reasoning_tokens=0,
        ),
        estimated_cost_usd=Decimal("0"),
        retrieved_count=0,
        citation_count=len(citations),
        cached=True,
    )
    _persist_trace(
        database_url=database_url,
        identifier_hash_key=identifier_hash_key,
        actor_subject=actor_subject,
        question=question,
        trace=trace,
    )
    return AnswerResult(
        status=status,
        answer=str(payload.get("answer", SAFE_REFUSAL)),
        citations=citations,
        trace=trace,
    )


def _store_cached_answer(
    *,
    database_url: str,
    identifier_hash_key: str,
    actor_subject: str,
    cache_key_hash: str,
    result: AnswerResult,
    cache_ttl_seconds: int,
) -> None:
    if cache_ttl_seconds == 0:
        return
    if not 1 <= cache_ttl_seconds <= 86_400:
        raise ValueError("RAG cache TTL is invalid.")
    payload = {
        "status": result.status,
        "answer": result.answer,
        "citations": [citation.model_dump(mode="json") for citation in result.citations],
        "model": result.trace.model,
    }
    with psycopg.connect(database_url) as connection:
        require_current_schema(connection)
        connection.execute(
            """
            INSERT INTO rag_cache (
                principal_hash, cache_key_hash, response, expires_at
            ) VALUES (%s, %s, %s, now() + make_interval(secs => %s))
            ON CONFLICT (principal_hash, cache_key_hash) DO UPDATE
            SET response = excluded.response, expires_at = excluded.expires_at,
                created_at = now()
            """,
            (
                _principal_hash(identifier_hash_key, actor_subject),
                cache_key_hash,
                Jsonb(payload),
                cache_ttl_seconds,
            ),
        )


def answer_question(
    *,
    database_url: str,
    identifier_hash_key: str,
    actor_subject: str,
    question: str,
    metadata_filter: dict[str, str],
    embedding_provider: EmbeddingProvider,
    answer_generator: AnswerGenerator,
    request_id: uuid.UUID | None = None,
    requests_per_minute: int = 0,
    daily_token_budget: int = 0,
    cache_ttl_seconds: int = 0,
    allow_degraded: bool = False,
) -> AnswerResult:
    """Retrieve authorized evidence, generate, and verify every citation before returning."""
    started_at = time.monotonic()
    request_id = request_id or uuid.uuid4()
    _enforce_request_rate(
        database_url=database_url,
        identifier_hash_key=identifier_hash_key,
        actor_subject=actor_subject,
        requests_per_minute=requests_per_minute,
    )
    cache_key_hash = _cache_key(
        identifier_hash_key=identifier_hash_key,
        question=question,
        metadata_filter=metadata_filter,
        embedding_provider=embedding_provider,
        answer_generator=answer_generator,
    )
    if cache_ttl_seconds:
        cached = _cached_answer(
            database_url=database_url,
            identifier_hash_key=identifier_hash_key,
            actor_subject=actor_subject,
            cache_key_hash=cache_key_hash,
            request_id=request_id,
            question=question,
        )
        if cached is not None:
            return cached
    hits = retrieve_chunks(
        database_url=database_url,
        identifier_hash_key=identifier_hash_key,
        actor_subject=actor_subject,
        query=question,
        embedding_provider=embedding_provider,
        mode="hybrid",
        limit=8,
        metadata_filter=metadata_filter,
    )
    evidence = sorted(
        (hit for hit in hits if evidence_is_sufficient(hit)),
        key=lambda hit: (
            -(hit.lexical_score or 0.0),
            -(hit.semantic_similarity or -1.0),
            -hit.score,
            str(hit.chunk_id),
        ),
    )
    if not evidence:
        trace = _refusal_trace(
            request_id=request_id,
            duration_ms=round((time.monotonic() - started_at) * 1000),
            retrieved_count=len(hits),
        )
        _persist_trace(
            database_url=database_url,
            identifier_hash_key=identifier_hash_key,
            actor_subject=actor_subject,
            question=question,
            trace=trace,
        )
        result = AnswerResult(status="refused", answer=SAFE_REFUSAL, citations=[], trace=trace)
        _store_cached_answer(
            database_url=database_url,
            identifier_hash_key=identifier_hash_key,
            actor_subject=actor_subject,
            cache_key_hash=cache_key_hash,
            result=result,
            cache_ttl_seconds=cache_ttl_seconds,
        )
        return result

    _enforce_daily_budget(
        database_url=database_url,
        identifier_hash_key=identifier_hash_key,
        actor_subject=actor_subject,
        daily_token_budget=daily_token_budget,
    )
    degraded = False
    try:
        generated = answer_generator.generate(question, evidence, request_id=str(request_id))
    except AIRefusalError:
        trace = _refusal_trace(
            request_id=request_id,
            duration_ms=round((time.monotonic() - started_at) * 1000),
            retrieved_count=len(evidence),
        )
        _persist_trace(
            database_url=database_url,
            identifier_hash_key=identifier_hash_key,
            actor_subject=actor_subject,
            question=question,
            trace=trace,
        )
        result = AnswerResult(status="refused", answer=SAFE_REFUSAL, citations=[], trace=trace)
        _store_cached_answer(
            database_url=database_url,
            identifier_hash_key=identifier_hash_key,
            actor_subject=actor_subject,
            cache_key_hash=cache_key_hash,
            result=result,
            cache_ttl_seconds=cache_ttl_seconds,
        )
        return result
    except AIProviderUnavailableError:
        if allow_degraded:
            generated = DeterministicGroundedGenerator().generate(
                question, evidence, request_id=str(request_id)
            )
            degraded = True
        else:
            unavailable_trace = RAGTrace(
                request_id=request_id,
                status="provider_unavailable",
                provider="answer_provider",
                model="unavailable",
                duration_ms=round((time.monotonic() - started_at) * 1000),
                usage=TokenUsage(
                    input_tokens=0,
                    output_tokens=0,
                    total_tokens=0,
                    cached_input_tokens=0,
                    reasoning_tokens=0,
                ),
                estimated_cost_usd=None,
                retrieved_count=len(evidence),
                citation_count=0,
            )
            _persist_trace(
                database_url=database_url,
                identifier_hash_key=identifier_hash_key,
                actor_subject=actor_subject,
                question=question,
                trace=unavailable_trace,
            )
            raise

    evidence_by_id = {str(hit.chunk_id): hit for hit in evidence}
    cited_ids = list(dict.fromkeys(generated.draft.cited_chunk_ids))
    citations_valid = bool(cited_ids) and all(chunk_id in evidence_by_id for chunk_id in cited_ids)
    if not generated.draft.supported or not citations_valid:
        trace = RAGTrace(
            request_id=request_id,
            status="refused",
            provider=generated.provider,
            model=generated.model,
            duration_ms=round((time.monotonic() - started_at) * 1000),
            usage=generated.usage,
            estimated_cost_usd=generated.estimated_cost_usd,
            retrieved_count=len(evidence),
            citation_count=0,
        )
        _persist_trace(
            database_url=database_url,
            identifier_hash_key=identifier_hash_key,
            actor_subject=actor_subject,
            question=question,
            trace=trace,
        )
        result = AnswerResult(status="refused", answer=SAFE_REFUSAL, citations=[], trace=trace)
        _store_cached_answer(
            database_url=database_url,
            identifier_hash_key=identifier_hash_key,
            actor_subject=actor_subject,
            cache_key_hash=cache_key_hash,
            result=result,
            cache_ttl_seconds=cache_ttl_seconds,
        )
        return result

    citations = [
        Citation(
            chunk_id=hit.chunk_id,
            document_id=hit.document_id,
            source_uri=hit.source_uri,
            title=hit.title,
            chunk_index=hit.chunk_index,
        )
        for hit in (evidence_by_id[chunk_id] for chunk_id in cited_ids)
    ]
    trace = RAGTrace(
        request_id=request_id,
        status="degraded" if degraded else "answered",
        provider=generated.provider,
        model=generated.model,
        duration_ms=round((time.monotonic() - started_at) * 1000),
        usage=generated.usage,
        estimated_cost_usd=generated.estimated_cost_usd,
        retrieved_count=len(evidence),
        citation_count=len(citations),
    )
    _persist_trace(
        database_url=database_url,
        identifier_hash_key=identifier_hash_key,
        actor_subject=actor_subject,
        question=question,
        trace=trace,
    )
    result = AnswerResult(
        status="degraded" if degraded else "answered",
        answer=generated.draft.answer,
        citations=citations,
        trace=trace,
    )
    _store_cached_answer(
        database_url=database_url,
        identifier_hash_key=identifier_hash_key,
        actor_subject=actor_subject,
        cache_key_hash=cache_key_hash,
        result=result,
        cache_ttl_seconds=cache_ttl_seconds,
    )
    return result
