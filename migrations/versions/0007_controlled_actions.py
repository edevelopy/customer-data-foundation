"""Add controlled action requests and append-only audit events.

Revision ID: 0007_controlled_actions
Revises: 0006_rag_traces
Create Date: 2026-07-18
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0007_controlled_actions"
down_revision: str | None = "0006_rag_traces"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create pending actions that cannot execute without a separate approval."""
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS action_requests (
            action_id uuid PRIMARY KEY,
            requester_hash char(64) NOT NULL,
            action_type varchar(80) NOT NULL CHECK (
                action_type IN ('send_customer_followup')
            ),
            arguments jsonb NOT NULL,
            arguments_sha256 char(64) NOT NULL,
            status varchar(24) NOT NULL CHECK (
                status IN ('pending', 'approved', 'executed', 'rejected', 'expired')
            ),
            planner_provider varchar(40) NOT NULL,
            planner_model varchar(120) NOT NULL,
            approver_hash char(64),
            approved_at timestamptz,
            executed_at timestamptz,
            result_code varchar(80),
            created_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT action_requests_arguments_object CHECK (
                jsonb_typeof(arguments) = 'object'
            )
        );

        CREATE INDEX IF NOT EXISTS action_requests_requester_created_idx
            ON action_requests (requester_hash, created_at DESC);

        CREATE TABLE IF NOT EXISTS action_audit_events (
            event_id uuid PRIMARY KEY,
            action_id uuid NOT NULL REFERENCES action_requests(action_id) ON DELETE CASCADE,
            actor_hash char(64) NOT NULL,
            event_type varchar(40) NOT NULL CHECK (
                event_type IN ('proposed', 'approved', 'executed', 'rejected')
            ),
            arguments_sha256 char(64) NOT NULL,
            result_code varchar(80),
            created_at timestamptz NOT NULL DEFAULT now()
        );

        CREATE INDEX IF NOT EXISTS action_audit_events_action_created_idx
            ON action_audit_events (action_id, created_at);
        """
    )


def downgrade() -> None:
    """Remove controlled action state."""
    op.execute(
        """
        DROP TABLE IF EXISTS action_audit_events;
        DROP TABLE IF EXISTS action_requests;
        """
    )
