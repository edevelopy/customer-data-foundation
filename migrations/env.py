"""Entorno de migraciones para PostgreSQL."""

from __future__ import annotations

from alembic import context
from sqlalchemy import engine_from_config, pool

from fde_foundation.settings import ConfigurationError, read_secret

config = context.config
target_metadata = None


def sqlalchemy_url() -> str:
    configured_url = config.attributes.get("database_url")
    if configured_url:
        url = str(configured_url)
    else:
        try:
            url = read_secret("DATABASE_URL", minimum_length=1)
        except ConfigurationError as error:
            raise RuntimeError("Database configuration is required to run migrations") from error
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


def run_migrations_offline() -> None:
    context.configure(
        url=sqlalchemy_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    section = config.get_section(config.config_ini_section, {})
    section["sqlalchemy.url"] = sqlalchemy_url()
    connectable = engine_from_config(
        section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()
    connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
