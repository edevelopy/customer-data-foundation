"""Add a durable integration outbox and simulated partner receipts.

Revision ID: 0004_integration_outbox
Revises: 0003_recovery_leases
Create Date: 2026-07-18
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0004_integration_outbox"
down_revision: str | None = "0003_recovery_leases"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Persist at-least-once delivery state without storing customer PII."""
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS integration_outbox (
            event_id uuid PRIMARY KEY,
            operation_id uuid NOT NULL UNIQUE
                REFERENCES api_operations(operation_id) ON DELETE CASCADE,
            event_type varchar(80) NOT NULL,
            payload jsonb NOT NULL,
            status varchar(24) NOT NULL DEFAULT 'pending',
            attempt_count integer NOT NULL DEFAULT 0,
            available_at timestamptz NOT NULL DEFAULT now(),
            lease_expires_at timestamptz,
            last_failure_code varchar(64),
            delivered_at timestamptz,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT integration_outbox_status_allowed CHECK (
                status IN ('pending', 'delivering', 'delivered', 'dead_letter')
            ),
            CONSTRAINT integration_outbox_attempt_count_nonnegative CHECK (attempt_count >= 0),
            CONSTRAINT integration_outbox_event_type_known CHECK (
                event_type = 'customer_import.completed'
            ),
            CONSTRAINT integration_outbox_payload_object CHECK (
                jsonb_typeof(payload) = 'object'
            )
        );

        CREATE INDEX IF NOT EXISTS integration_outbox_dispatch_idx
            ON integration_outbox (available_at, created_at)
            WHERE status IN ('pending', 'delivering');

        CREATE TABLE IF NOT EXISTS partner_delivery_attempts (
            event_id uuid PRIMARY KEY,
            attempt_count integer NOT NULL DEFAULT 0 CHECK (attempt_count >= 0),
            updated_at timestamptz NOT NULL DEFAULT now()
        );

        CREATE TABLE IF NOT EXISTS partner_receipts (
            event_id uuid PRIMARY KEY,
            body_sha256 char(64) NOT NULL,
            received_at timestamptz NOT NULL DEFAULT now()
        );
        """
    )


def downgrade() -> None:
    """Remove simulator and delivery state without changing customer data."""
    op.execute(
        """
        DROP TABLE IF EXISTS partner_receipts;
        DROP TABLE IF EXISTS partner_delivery_attempts;
        DROP TABLE IF EXISTS integration_outbox;
        """
    )
