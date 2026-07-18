"""Versioned document ingestion and permission-scoped hybrid retrieval."""

from __future__ import annotations

import hashlib
import re
import uuid
from dataclasses import dataclass
from typing import Any, Literal

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from fde_foundation.api_store import protected_hash
from fde_foundation.database import require_current_schema
from fde_foundation.embeddings import EmbeddingProvider, vector_literal

MAX_DOCUMENT_CHARACTERS = 100_000
CHUNK_CHARACTERS = 800
CHUNK_OVERLAP_CHARACTERS = 120
INJECTION_PATTERN = re.compile(
    r"(?:ignore|disregard|reveal|override).{0,40}(?:instruction|prompt|system|secret)",
    re.IGNORECASE,
)
LEXICAL_STOPWORDS = frozenset(
    {
        "and",
        "are",
        "como",
        "can",
        "cual",
        "cuales",
        "del",
        "desde",
        "donde",
        "does",
        "el",
        "ella",
        "en",
        "es",
        "esta",
        "for",
        "how",
        "is",
        "la",
        "las",
        "los",
        "may",
        "para",
        "por",
        "que",
        "the",
        "una",
        "what",
        "when",
        "where",
        "who",
        "with",
    }
)


@dataclass(frozen=True)
class DocumentRecord:
    document_id: uuid.UUID
    source_uri: str
    title: str
    version: int
    chunk_count: int
    permission_count: int
    embedding_provider: str
    embedding_model: str
    reused: bool


@dataclass(frozen=True)
class RetrievalHit:
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    source_uri: str
    title: str
    chunk_index: int
    content: str
    metadata: dict[str, Any]
    score: float
    lexical_rank: int | None
    semantic_rank: int | None
    lexical_score: float | None
    semantic_similarity: float | None


def chunk_text(content: str) -> list[str]:
    normalized = re.sub(r"[ \t]+", " ", content.replace("\r\n", "\n")).strip()
    if not normalized or len(normalized) > MAX_DOCUMENT_CHARACTERS:
        raise ValueError("Document content is empty or exceeds the bounded size.")
    chunks: list[str] = []
    start = 0
    while start < len(normalized):
        end = min(start + CHUNK_CHARACTERS, len(normalized))
        if end < len(normalized):
            boundary = max(normalized.rfind("\n", start, end), normalized.rfind(". ", start, end))
            if boundary > start + CHUNK_CHARACTERS // 2:
                end = boundary + 1
        chunk = normalized[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(normalized):
            break
        start = max(start + 1, end - CHUNK_OVERLAP_CHARACTERS)
    return chunks


def token_estimate(content: str) -> int:
    return max(1, (len(content) + 3) // 4)


def lexical_query(content: str) -> str:
    """Build a bounded OR query from words only; never pass user operators to to_tsquery."""
    terms = [
        term
        for term in dict.fromkeys(re.findall(r"[\w]{2,40}", content.casefold(), re.UNICODE))
        if term not in LEXICAL_STOPWORDS
    ][:30]
    return " | ".join(terms)


def ingest_document(
    *,
    database_url: str,
    identifier_hash_key: str,
    actor_subject: str,
    reader_subjects: list[str],
    source_uri: str,
    title: str,
    content: str,
    metadata: dict[str, Any],
    embedding_provider: EmbeddingProvider,
) -> DocumentRecord:
    chunks = chunk_text(content)
    vectors = embedding_provider.embed(chunks)
    content_sha256 = hashlib.sha256(content.encode("utf-8")).hexdigest()
    actor_hash = protected_hash(identifier_hash_key, "knowledge-principal", actor_subject)
    reader_hashes = {
        protected_hash(identifier_hash_key, "knowledge-principal", subject)
        for subject in [actor_subject, *reader_subjects]
    }
    safe_metadata = dict(metadata)
    safe_metadata["untrusted_instruction_detected"] = bool(INJECTION_PATTERN.search(content))
    safe_metadata["embedding_provider"] = embedding_provider.name
    safe_metadata["embedding_model"] = embedding_provider.model

    with (
        psycopg.connect(database_url, row_factory=dict_row) as connection,
        connection.transaction(),
    ):
        require_current_schema(connection)
        existing = connection.execute(
            """
            SELECT document_id, version
            FROM knowledge_documents
            WHERE created_by_hash = %s AND source_uri = %s AND content_sha256 = %s
            """,
            (actor_hash, source_uri, content_sha256),
        ).fetchone()
        reused = existing is not None
        if existing:
            document_id = existing["document_id"]
            version = existing["version"]
        else:
            connection.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
                (f"{actor_hash}:{source_uri}",),
            )
            previous = connection.execute(
                """
                SELECT coalesce(max(version), 0) AS latest
                FROM knowledge_documents
                WHERE created_by_hash = %s AND source_uri = %s
                """,
                (actor_hash, source_uri),
            ).fetchone()
            version = int(previous["latest"]) + 1 if previous else 1
            connection.execute(
                """
                UPDATE knowledge_documents SET active = false
                WHERE created_by_hash = %s AND source_uri = %s AND active
                """,
                (actor_hash, source_uri),
            )
            document_id = uuid.uuid4()
            connection.execute(
                """
                INSERT INTO knowledge_documents (
                    document_id, source_uri, title, version, content_sha256,
                    created_by_hash, metadata
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    document_id,
                    source_uri,
                    title,
                    version,
                    content_sha256,
                    actor_hash,
                    Jsonb(safe_metadata),
                ),
            )
            for index, (chunk, vector) in enumerate(zip(chunks, vectors, strict=True)):
                chunk_metadata = {
                    "document_version": version,
                    "untrusted_instruction_detected": bool(INJECTION_PATTERN.search(chunk)),
                }
                connection.execute(
                    """
                    INSERT INTO knowledge_chunks (
                        chunk_id, document_id, chunk_index, content, content_sha256,
                        token_estimate, metadata, embedding
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s::vector)
                    """,
                    (
                        uuid.uuid4(),
                        document_id,
                        index,
                        chunk,
                        hashlib.sha256(chunk.encode("utf-8")).hexdigest(),
                        token_estimate(chunk),
                        Jsonb(chunk_metadata),
                        vector_literal(vector),
                    ),
                )
        for reader_hash in reader_hashes:
            connection.execute(
                """
                INSERT INTO knowledge_document_permissions (
                    document_id, principal_hash, granted_by_hash
                ) VALUES (%s, %s, %s)
                ON CONFLICT (document_id, principal_hash) DO NOTHING
                """,
                (document_id, reader_hash, actor_hash),
            )
        permission_count = connection.execute(
            "SELECT count(*) AS total FROM knowledge_document_permissions WHERE document_id = %s",
            (document_id,),
        ).fetchone()
    return DocumentRecord(
        document_id=document_id,
        source_uri=source_uri,
        title=title,
        version=version,
        chunk_count=len(chunks),
        permission_count=int(permission_count["total"]) if permission_count else 0,
        embedding_provider=embedding_provider.name,
        embedding_model=embedding_provider.model,
        reused=reused,
    )


def retrieve_chunks(
    *,
    database_url: str,
    identifier_hash_key: str,
    actor_subject: str,
    query: str,
    embedding_provider: EmbeddingProvider,
    mode: Literal["lexical", "semantic", "hybrid"] = "hybrid",
    limit: int = 5,
    metadata_filter: dict[str, Any] | None = None,
) -> list[RetrievalHit]:
    if not query.strip() or not 1 <= limit <= 20:
        raise ValueError("Query and limit are invalid.")
    actor_hash = protected_hash(identifier_hash_key, "knowledge-principal", actor_subject)
    query_vector = vector_literal(embedding_provider.embed([query])[0])
    lexical_query_value = lexical_query(query)
    metadata_filter = metadata_filter or {}
    common_params: tuple[Any, ...] = (actor_hash, Jsonb(metadata_filter))
    base_select = """
        SELECT c.chunk_id, c.document_id, d.source_uri, d.title, c.chunk_index,
               c.content, c.metadata
        FROM knowledge_chunks c
        JOIN knowledge_documents d ON d.document_id = c.document_id AND d.active
        JOIN knowledge_document_permissions p ON p.document_id = d.document_id
        WHERE p.principal_hash = %s AND d.metadata @> %s::jsonb
    """
    lexical_rows: list[dict[str, Any]] = []
    semantic_rows: list[dict[str, Any]] = []
    with psycopg.connect(database_url, row_factory=dict_row) as connection:
        require_current_schema(connection)
        if mode in {"lexical", "hybrid"} and lexical_query_value:
            lexical_rows = connection.execute(
                base_select.replace(
                    "c.content, c.metadata",
                    "c.content, c.metadata, "
                    "ts_rank_cd(c.search_vector, to_tsquery('simple', %s)) "
                    "AS lexical_score",
                )
                + """
                  AND c.search_vector @@ to_tsquery('simple', %s)
                ORDER BY ts_rank_cd(c.search_vector, to_tsquery('simple', %s)) DESC,
                         c.chunk_id
                LIMIT %s
                """,
                (
                    lexical_query_value,
                    *common_params,
                    lexical_query_value,
                    lexical_query_value,
                    max(limit, 20),
                ),
            ).fetchall()
        if mode in {"semantic", "hybrid"}:
            semantic_rows = connection.execute(
                base_select.replace(
                    "c.content, c.metadata",
                    "c.content, c.metadata, "
                    "1 - (c.embedding <=> %s::vector) AS semantic_similarity",
                )
                + """
                ORDER BY c.embedding <=> %s::vector, c.chunk_id
                LIMIT %s
                """,
                (query_vector, *common_params, query_vector, max(limit, 20)),
            ).fetchall()

    combined: dict[uuid.UUID, dict[str, Any]] = {}
    for rank, row in enumerate(lexical_rows, start=1):
        combined.setdefault(row["chunk_id"], dict(row))["lexical_rank"] = rank
    for rank, row in enumerate(semantic_rows, start=1):
        target = combined.setdefault(row["chunk_id"], dict(row))
        target["semantic_rank"] = rank
        target["semantic_similarity"] = row["semantic_similarity"]
    hits: list[RetrievalHit] = []
    for row in combined.values():
        lexical_rank = row.get("lexical_rank")
        semantic_rank = row.get("semantic_rank")
        score = (0.5 / (60 + lexical_rank) if lexical_rank else 0.0) + (
            0.5 / (60 + semantic_rank) if semantic_rank else 0.0
        )
        hits.append(
            RetrievalHit(
                chunk_id=row["chunk_id"],
                document_id=row["document_id"],
                source_uri=row["source_uri"],
                title=row["title"],
                chunk_index=row["chunk_index"],
                content=row["content"],
                metadata=dict(row["metadata"]),
                score=score,
                lexical_rank=lexical_rank,
                semantic_rank=semantic_rank,
                lexical_score=(
                    float(row["lexical_score"]) if row.get("lexical_score") is not None else None
                ),
                semantic_similarity=(
                    float(row["semantic_similarity"])
                    if row.get("semantic_similarity") is not None
                    else None
                ),
            )
        )
    hits.sort(key=lambda hit: (-hit.score, str(hit.chunk_id)))
    return hits[:limit]
