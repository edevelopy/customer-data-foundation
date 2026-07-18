"""Create API operation tracking.

Revision ID: 0002_api_operations
Revises: 0001_customer_imports
Create Date: 2026-07-18
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0002_api_operations"
down_revision: str | None = "0001_customer_imports"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Persist idempotent API operations without raw identity or idempotency keys."""
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS api_operations (
            operation_id uuid PRIMARY KEY,
            actor_hash char(64) NOT NULL,
            idempotency_key_hash char(64) NOT NULL,
            request_sha256 char(64) NOT NULL,
            status varchar(32) NOT NULL,
            accepted boolean NOT NULL DEFAULT false,
            total_rows integer NOT NULL DEFAULT 0 CHECK (total_rows >= 0),
            inserted_rows integer NOT NULL DEFAULT 0 CHECK (inserted_rows >= 0),
            existing_rows integer NOT NULL DEFAULT 0 CHECK (existing_rows >= 0),
            duration_ms integer NOT NULL DEFAULT 0 CHECK (duration_ms >= 0),
            error_codes text[] NOT NULL DEFAULT '{}',
            issues jsonb NOT NULL DEFAULT '[]'::jsonb,
            created_at timestamptz NOT NULL DEFAULT now(),
            completed_at timestamptz,
            CONSTRAINT api_operations_actor_idempotency_unique
                UNIQUE (actor_hash, idempotency_key_hash),
            CONSTRAINT api_operations_status_allowed CHECK (
                status IN (
                    'processing', 'imported', 'already_imported', 'validation_failed',
                    'conflict', 'configuration_error', 'migration_required', 'database_error'
                )
            )
        );

        CREATE INDEX IF NOT EXISTS api_operations_created_at_idx
            ON api_operations (created_at DESC);
        """
    )


def downgrade() -> None:
    """Remove API operation tracking."""
    op.execute("DROP TABLE IF EXISTS api_operations;")
