"""Add permission-scoped enterprise documents and pgvector chunks.

Revision ID: 0005_enterprise_knowledge
Revises: 0004_integration_outbox
Create Date: 2026-07-18
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0005_enterprise_knowledge"
down_revision: str | None = "0004_integration_outbox"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create versioned knowledge records with explicit read permissions."""
    op.execute(
        """
        CREATE EXTENSION IF NOT EXISTS vector;

        CREATE TABLE IF NOT EXISTS knowledge_documents (
            document_id uuid PRIMARY KEY,
            source_uri varchar(500) NOT NULL,
            title varchar(200) NOT NULL,
            version integer NOT NULL CHECK (version >= 1),
            content_sha256 char(64) NOT NULL,
            created_by_hash char(64) NOT NULL,
            metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
            active boolean NOT NULL DEFAULT true,
            created_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT knowledge_documents_metadata_object CHECK (
                jsonb_typeof(metadata) = 'object'
            ),
            UNIQUE (created_by_hash, source_uri, content_sha256)
        );

        CREATE UNIQUE INDEX IF NOT EXISTS knowledge_documents_one_active_source_idx
            ON knowledge_documents (created_by_hash, source_uri)
            WHERE active;

        CREATE TABLE IF NOT EXISTS knowledge_document_permissions (
            document_id uuid NOT NULL REFERENCES knowledge_documents(document_id) ON DELETE CASCADE,
            principal_hash char(64) NOT NULL,
            granted_by_hash char(64) NOT NULL,
            granted_at timestamptz NOT NULL DEFAULT now(),
            PRIMARY KEY (document_id, principal_hash)
        );

        CREATE INDEX IF NOT EXISTS knowledge_document_permissions_principal_idx
            ON knowledge_document_permissions (principal_hash, document_id);

        CREATE TABLE IF NOT EXISTS knowledge_chunks (
            chunk_id uuid PRIMARY KEY,
            document_id uuid NOT NULL REFERENCES knowledge_documents(document_id) ON DELETE CASCADE,
            chunk_index integer NOT NULL CHECK (chunk_index >= 0),
            content text NOT NULL CHECK (length(content) BETWEEN 1 AND 4000),
            content_sha256 char(64) NOT NULL,
            token_estimate integer NOT NULL CHECK (token_estimate >= 1),
            metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
            embedding vector(256) NOT NULL,
            search_vector tsvector GENERATED ALWAYS AS (
                to_tsvector('simple', coalesce(content, ''))
            ) STORED,
            created_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT knowledge_chunks_metadata_object CHECK (jsonb_typeof(metadata) = 'object'),
            UNIQUE (document_id, chunk_index)
        );

        CREATE INDEX IF NOT EXISTS knowledge_chunks_search_idx
            ON knowledge_chunks USING gin (search_vector);
        CREATE INDEX IF NOT EXISTS knowledge_chunks_embedding_idx
            ON knowledge_chunks USING hnsw (embedding vector_cosine_ops);
        CREATE INDEX IF NOT EXISTS knowledge_chunks_document_idx
            ON knowledge_chunks (document_id, chunk_index);
        """
    )


def downgrade() -> None:
    """Remove enterprise knowledge without removing the shared vector extension."""
    op.execute(
        """
        DROP TABLE IF EXISTS knowledge_chunks;
        DROP TABLE IF EXISTS knowledge_document_permissions;
        DROP TABLE IF EXISTS knowledge_documents;
        """
    )
