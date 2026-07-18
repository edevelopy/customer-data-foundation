"""Create customer import tables.

Revision ID: 0001_customer_imports
Revises: None
Create Date: 2026-07-18
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0001_customer_imports"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the initial schema, adopting identical pilot tables when present."""
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS import_batches (
            id uuid PRIMARY KEY,
            file_sha256 char(64) NOT NULL UNIQUE,
            row_count integer NOT NULL CHECK (row_count >= 0),
            inserted_count integer NOT NULL CHECK (inserted_count >= 0),
            existing_count integer NOT NULL CHECK (existing_count >= 0),
            created_at timestamptz NOT NULL DEFAULT now()
        );

        CREATE TABLE IF NOT EXISTS customers (
            id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            email varchar(254) NOT NULL UNIQUE,
            first_name varchar(80) NOT NULL,
            last_name varchar(80) NOT NULL,
            phone varchar(16) NOT NULL DEFAULT '',
            source varchar(50) NOT NULL,
            import_batch_id uuid NOT NULL REFERENCES import_batches(id),
            created_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT customers_email_normalized CHECK (email = lower(btrim(email))),
            CONSTRAINT customers_email_shape CHECK (position('@' IN email) > 1),
            CONSTRAINT customers_first_name_nonempty CHECK (length(btrim(first_name)) > 0),
            CONSTRAINT customers_last_name_nonempty CHECK (length(btrim(last_name)) > 0),
            CONSTRAINT customers_phone_e164
                CHECK (phone = '' OR phone ~ '^\\+[1-9][0-9]{7,14}$'),
            CONSTRAINT customers_source_nonempty CHECK (length(btrim(source)) > 0)
        );
        """
    )


def downgrade() -> None:
    """Remove the complete pilot schema."""
    op.execute("DROP TABLE IF EXISTS customers;")
    op.execute("DROP TABLE IF EXISTS import_batches;")
