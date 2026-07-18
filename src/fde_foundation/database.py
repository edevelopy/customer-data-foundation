"""Configuracion programatica de las migraciones de PostgreSQL."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any, Final

import psycopg
from alembic import command
from alembic.config import Config

CURRENT_SCHEMA_REVISION: Final = "0005_enterprise_knowledge"
PROJECT_ROOT: Final = Path(__file__).resolve().parents[2]
CONNECT_TIMEOUT_SECONDS: Final = 5
POSTGRES_OPERATION_LIMITS: Final = "-c statement_timeout=10000 -c lock_timeout=3000"
RECOVERY_LEASE_SECONDS: Final = 6 * 60


class SchemaNotCurrentError(Exception):
    """La base existe, pero no tiene la revision requerida por la aplicacion."""


def migration_config(database_url: str) -> Config:
    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(PROJECT_ROOT / "migrations"))
    config.attributes["database_url"] = database_url
    return config


def upgrade_database(database_url: str) -> None:
    """Aplica todas las migraciones pendientes."""
    command.upgrade(migration_config(database_url), "head")


def downgrade_database(database_url: str) -> None:
    """Revierte el esquema completo; solo debe usarse en una base desechable."""
    command.downgrade(migration_config(database_url), "base")


def require_current_schema(connection: psycopg.Connection[Any]) -> None:
    """Comprueba la revision sin modificar la base de datos."""
    version_table = connection.execute("SELECT to_regclass('public.alembic_version');").fetchone()
    if not version_table:
        raise SchemaNotCurrentError
    relation = (
        next(iter(version_table.values()))
        if isinstance(version_table, Mapping)
        else version_table[0]
    )
    if relation is None:
        raise SchemaNotCurrentError
    revision = connection.execute("SELECT version_num FROM alembic_version;").fetchone()
    if not revision:
        raise SchemaNotCurrentError
    version = next(iter(revision.values())) if isinstance(revision, Mapping) else revision[0]
    if version != CURRENT_SCHEMA_REVISION:
        raise SchemaNotCurrentError
