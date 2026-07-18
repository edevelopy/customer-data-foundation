"""Add recoverable leases to API operations.

Revision ID: 0003_recovery_leases
Revises: 0002_api_operations
Create Date: 2026-07-18
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0003_recovery_leases"
down_revision: str | None = "0002_api_operations"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Allow an abandoned synchronous request to be reclaimed safely."""
    op.execute(
        """
        ALTER TABLE api_operations
            ADD COLUMN IF NOT EXISTS lease_expires_at timestamptz
                NOT NULL DEFAULT (now() + interval '6 minutes'),
            ADD COLUMN IF NOT EXISTS attempt_count integer NOT NULL DEFAULT 1,
            ADD COLUMN IF NOT EXISTS recovered_at timestamptz;

        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'api_operations_attempt_count_positive'
            ) THEN
                ALTER TABLE api_operations
                    ADD CONSTRAINT api_operations_attempt_count_positive
                    CHECK (attempt_count >= 1);
            END IF;
        END $$;

        CREATE INDEX IF NOT EXISTS api_operations_expired_processing_idx
            ON api_operations (lease_expires_at)
            WHERE status = 'processing';
        """
    )


def downgrade() -> None:
    """Remove recovery metadata without changing operation results."""
    op.execute(
        """
        DROP INDEX IF EXISTS api_operations_expired_processing_idx;
        ALTER TABLE api_operations
            DROP COLUMN IF EXISTS recovered_at,
            DROP COLUMN IF EXISTS attempt_count,
            DROP COLUMN IF EXISTS lease_expires_at;
        """
    )
