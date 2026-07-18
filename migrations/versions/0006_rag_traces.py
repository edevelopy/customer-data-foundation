"""Add privacy-safe RAG traces and principal-scoped cache.

Revision ID: 0006_rag_traces
Revises: 0005_enterprise_knowledge
Create Date: 2026-07-18
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0006_rag_traces"
down_revision: str | None = "0005_enterprise_knowledge"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create traces without raw questions, answers, subjects or document content."""
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS rag_traces (
            request_id uuid PRIMARY KEY,
            principal_hash char(64) NOT NULL,
            query_hash char(64) NOT NULL,
            status varchar(24) NOT NULL CHECK (
                status IN ('answered', 'refused', 'degraded', 'provider_unavailable')
            ),
            provider varchar(40) NOT NULL,
            model varchar(120) NOT NULL,
            prompt_version varchar(40) NOT NULL,
            duration_ms integer NOT NULL CHECK (duration_ms >= 0),
            input_tokens integer NOT NULL CHECK (input_tokens >= 0),
            output_tokens integer NOT NULL CHECK (output_tokens >= 0),
            estimated_cost_usd numeric(18, 8),
            retrieved_count integer NOT NULL CHECK (retrieved_count >= 0),
            citation_count integer NOT NULL CHECK (citation_count >= 0),
            cached boolean NOT NULL DEFAULT false,
            created_at timestamptz NOT NULL DEFAULT now()
        );

        CREATE INDEX IF NOT EXISTS rag_traces_principal_created_idx
            ON rag_traces (principal_hash, created_at DESC);

        CREATE TABLE IF NOT EXISTS rag_cache (
            principal_hash char(64) NOT NULL,
            cache_key_hash char(64) NOT NULL,
            response jsonb NOT NULL,
            expires_at timestamptz NOT NULL,
            created_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT rag_cache_response_object CHECK (jsonb_typeof(response) = 'object'),
            PRIMARY KEY (principal_hash, cache_key_hash)
        );

        CREATE INDEX IF NOT EXISTS rag_cache_expiry_idx ON rag_cache (expires_at);
        """
    )


def downgrade() -> None:
    """Remove RAG traces and cache."""
    op.execute(
        """
        DROP TABLE IF EXISTS rag_cache;
        DROP TABLE IF EXISTS rag_traces;
        """
    )
