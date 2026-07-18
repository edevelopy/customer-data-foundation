from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta

import jwt
import psycopg
import pytest
from fastapi.testclient import TestClient

from fde_foundation.api import app
from fde_foundation.database import upgrade_database
from fde_foundation.embeddings import DeterministicEmbeddingProvider
from fde_foundation.knowledge import chunk_text, ingest_document, retrieve_chunks

DATABASE_URL = "postgresql://fde_test:test-only-password@localhost:55435/fde_test"
HASH_KEY = "test-knowledge-hash-key-with-more-than-thirty-two-characters"
JWT_SECRET = "test-jwt-signing-key-with-more-than-thirty-two-characters"
JWT_ISSUER = "fde-test"
JWT_AUDIENCE = "fde-knowledge-test"


@pytest.fixture
def database_url() -> str:
    url = os.environ.get(
        "PHASE4_TEST_DATABASE_URL", os.environ.get("TEST_DATABASE_URL", DATABASE_URL)
    )
    upgrade_database(url)
    with psycopg.connect(url) as connection:
        connection.execute(
            "TRUNCATE knowledge_chunks, knowledge_document_permissions, knowledge_documents CASCADE"
        )
    return url


def ingest(
    database_url: str,
    *,
    actor: str,
    readers: list[str],
    source: str,
    content: str,
    department: str = "support",
):
    return ingest_document(
        database_url=database_url,
        identifier_hash_key=HASH_KEY,
        actor_subject=actor,
        reader_subjects=readers,
        source_uri=source,
        title=source.rsplit("/", 1)[-1],
        content=content,
        metadata={"department": department},
        embedding_provider=DeterministicEmbeddingProvider(),
    )


def token(subject: str, roles: list[str]) -> str:
    now = datetime.now(UTC)
    return jwt.encode(
        {
            "sub": subject,
            "roles": roles,
            "iss": JWT_ISSUER,
            "aud": JWT_AUDIENCE,
            "iat": now,
            "exp": now + timedelta(minutes=10),
        },
        JWT_SECRET,
        algorithm="HS256",
    )


def auth(subject: str, roles: list[str]) -> dict[str, str]:
    return {"Authorization": f"Bearer {token(subject, roles)}"}


@pytest.fixture
def api_client(database_url: str, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("JWT_SECRET", JWT_SECRET)
    monkeypatch.setenv("IDENTIFIER_HASH_KEY", HASH_KEY)
    monkeypatch.setenv("METRICS_TOKEN", "metrics-token-with-more-than-thirty-two-characters")
    monkeypatch.setenv("JWT_ISSUER", JWT_ISSUER)
    monkeypatch.setenv("JWT_AUDIENCE", JWT_AUDIENCE)
    monkeypatch.setenv("EMBEDDING_PROVIDER", "deterministic_local")
    with TestClient(app) as client:
        yield client


def test_chunking_is_bounded_and_overlapping() -> None:
    content = " ".join(f"word-{index}" for index in range(400))
    chunks = chunk_text(content)

    assert len(chunks) > 1
    assert all(1 <= len(chunk) <= 800 for chunk in chunks)
    assert set(chunks[0].split()[-5:]) & set(chunks[1].split()[:20])


@pytest.mark.integration
def test_ingestion_is_reproducible_and_versions_changed_content(database_url: str) -> None:
    first = ingest(
        database_url,
        actor="owner",
        readers=["alice"],
        source="kb://refunds",
        content="Refunds are available within thirty days with a receipt.",
    )
    replay = ingest(
        database_url,
        actor="owner",
        readers=["alice", "bob"],
        source="kb://refunds",
        content="Refunds are available within thirty days with a receipt.",
    )
    changed = ingest(
        database_url,
        actor="owner",
        readers=["alice"],
        source="kb://refunds",
        content="Refunds are available within forty-five days with a receipt.",
    )

    assert first.version == 1
    assert replay.document_id == first.document_id
    assert replay.reused is True
    assert replay.permission_count == 3
    assert changed.version == 2
    assert changed.document_id != first.document_id


@pytest.mark.integration
def test_hybrid_retrieval_enforces_document_permissions_and_metadata(database_url: str) -> None:
    ingest(
        database_url,
        actor="owner",
        readers=["alice"],
        source="kb://refunds",
        content="Refund policy: customers may request a refund within thirty days.",
    )
    ingest(
        database_url,
        actor="owner",
        readers=["bob"],
        source="kb://payroll",
        content="Payroll records contain confidential employee salary information.",
        department="finance",
    )

    alice_hits = retrieve_chunks(
        database_url=database_url,
        identifier_hash_key=HASH_KEY,
        actor_subject="alice",
        query="refund policy",
        embedding_provider=DeterministicEmbeddingProvider(),
        mode="hybrid",
        metadata_filter={"department": "support"},
    )
    bob_hits = retrieve_chunks(
        database_url=database_url,
        identifier_hash_key=HASH_KEY,
        actor_subject="bob",
        query="refund policy",
        embedding_provider=DeterministicEmbeddingProvider(),
        mode="hybrid",
    )
    unknown_hits = retrieve_chunks(
        database_url=database_url,
        identifier_hash_key=HASH_KEY,
        actor_subject="mallory",
        query="salary",
        embedding_provider=DeterministicEmbeddingProvider(),
        mode="hybrid",
    )

    assert [hit.source_uri for hit in alice_hits] == ["kb://refunds"]
    assert all(hit.source_uri != "kb://refunds" for hit in bob_hits)
    assert unknown_hits == []


@pytest.mark.integration
@pytest.mark.parametrize("mode", ["lexical", "semantic", "hybrid"])
def test_each_retrieval_mode_returns_authorized_evidence(database_url: str, mode: str) -> None:
    ingest(
        database_url,
        actor="owner",
        readers=["alice"],
        source="kb://support-hours",
        content="Support hours are Monday through Friday from nine to five Eastern time.",
    )

    hits = retrieve_chunks(
        database_url=database_url,
        identifier_hash_key=HASH_KEY,
        actor_subject="alice",
        query="support hours Monday",
        embedding_provider=DeterministicEmbeddingProvider(),
        mode=mode,  # type: ignore[arg-type]
    )

    assert hits
    assert hits[0].source_uri == "kb://support-hours"


@pytest.mark.integration
def test_knowledge_http_contract_preserves_authorization(api_client: TestClient) -> None:
    created = api_client.post(
        "/v1/knowledge/documents",
        headers=auth("owner", ["operator"]),
        json={
            "source_uri": "kb://returns",
            "title": "Returns",
            "content": "Returns require an authorization number from the support team.",
            "readers": ["alice"],
            "metadata": {"department": "support"},
        },
    )
    alice = api_client.post(
        "/v1/knowledge/retrieval",
        headers=auth("alice", ["operator"]),
        json={"query": "returns authorization number", "mode": "hybrid"},
    )
    bob = api_client.post(
        "/v1/knowledge/retrieval",
        headers=auth("bob", ["operator"]),
        json={"query": "returns authorization number", "mode": "hybrid"},
    )
    forbidden = api_client.post(
        "/v1/knowledge/documents",
        headers=auth("auditor", ["auditor"]),
        json={
            "source_uri": "kb://forbidden",
            "title": "Forbidden",
            "content": "This should not be accepted.",
        },
    )

    assert created.status_code == 200
    assert created.json()["permission_count"] == 2
    assert "content" not in created.json()
    assert [hit["source_uri"] for hit in alice.json()["hits"]] == ["kb://returns"]
    assert bob.json()["hits"] == []
    assert forbidden.status_code == 403
