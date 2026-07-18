"""Crea y verifica backups PostgreSQL usando una restauracion aislada real."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import secrets
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

from fde_foundation.database import CURRENT_SCHEMA_REVISION

PROJECT_PATTERN: Final = re.compile(r"^[a-z0-9][a-z0-9_-]{0,62}$")
ARCHIVE_VERSION: Final = 1
SAFE_COUNTS_SQL: Final = (
    "SELECT (SELECT count(*) FROM import_batches),"
    "(SELECT count(*) FROM customers),"
    "(SELECT count(*) FROM api_operations),"
    "(SELECT count(*) FROM integration_outbox),"
    "(SELECT count(*) FROM partner_receipts),"
    "(SELECT version_num FROM alembic_version);"
)


def container_name(project_name: str) -> str:
    if not PROJECT_PATTERN.fullmatch(project_name):
        raise ValueError("invalid backup project name")
    return f"{project_name}-database-1"


def database_command(container: str, *command: str, stdin=None, stdout=None) -> None:
    subprocess.run(
        ["docker", "exec", "-i", container, "sh", "-ceu", *command],
        check=True,
        stdin=stdin,
        stdout=stdout,
    )


def query_counts(container: str, database: str = "fde_release") -> dict[str, int | str]:
    completed = subprocess.run(
        [
            "docker",
            "exec",
            container,
            "sh",
            "-ceu",
            'export PGPASSWORD="$(cat /run/secrets/postgres_password)"; '
            'exec psql -XAt -F "," -U fde_release -d "$1" -c "$2"',
            "backup-query",
            database,
            SAFE_COUNTS_SQL,
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    fields = completed.stdout.strip().split(",")
    if len(fields) != 6:
        raise ValueError("backup verification query returned invalid evidence")
    return {
        "import_batches": int(fields[0]),
        "customers": int(fields[1]),
        "api_operations": int(fields[2]),
        "integration_outbox": int(fields[3]),
        "partner_receipts": int(fields[4]),
        "schema_revision": fields[5],
    }


def private_output(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    return os.fdopen(descriptor, "wb")


def write_private_json(path: Path, payload: dict[str, object]) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as output:
        json.dump(payload, output, indent=2, sort_keys=True)
        output.write("\n")


def archive_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def create_backup(project_name: str, archive: Path) -> dict[str, object]:
    container = container_name(project_name)
    manifest_path = archive.with_suffix(archive.suffix + ".json")
    try:
        with private_output(archive) as output:
            database_command(
                container,
                'export PGPASSWORD="$(cat /run/secrets/postgres_password)"; '
                "exec pg_dump -U fde_release -d fde_release --format=custom "
                "--no-owner --no-privileges",
                stdout=output,
            )
        digest = archive_sha256(archive)
        counts = query_counts(container)
        if counts["schema_revision"] != CURRENT_SCHEMA_REVISION:
            raise ValueError("source database schema is not current")
        manifest: dict[str, object] = {
            "archive_format": "postgresql-custom",
            "archive_sha256": digest,
            "created_at": datetime.now(UTC).isoformat(),
            "format_version": ARCHIVE_VERSION,
            "safe_counts": counts,
        }
        write_private_json(manifest_path, manifest)
    except BaseException:
        archive.unlink(missing_ok=True)
        manifest_path.unlink(missing_ok=True)
        raise
    return manifest


def verify_backup(project_name: str, archive: Path) -> dict[str, object]:
    container = container_name(project_name)
    manifest_path = archive.with_suffix(archive.suffix + ".json")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict) or manifest.get("format_version") != ARCHIVE_VERSION:
        raise ValueError("backup manifest is invalid")
    digest = archive_sha256(archive)
    if not secrets.compare_digest(str(manifest.get("archive_sha256", "")), digest):
        raise ValueError("backup digest does not match manifest")

    database = f"fde_restore_{secrets.token_hex(6)}"
    database_command(
        container,
        'export PGPASSWORD="$(cat /run/secrets/postgres_password)"; '
        'exec createdb -U fde_release --template=template0 "$1"',
        "backup-create",
        database,
    )
    try:
        with archive.open("rb") as source:
            database_command(
                container,
                'export PGPASSWORD="$(cat /run/secrets/postgres_password)"; '
                'exec pg_restore -U fde_release --dbname="$1" --no-owner --no-privileges',
                "backup-restore",
                database,
                stdin=source,
            )
        restored = query_counts(container, database)
        if restored != manifest.get("safe_counts"):
            raise ValueError("restored database evidence differs from backup manifest")
    finally:
        database_command(
            container,
            'export PGPASSWORD="$(cat /run/secrets/postgres_password)"; '
            'exec dropdb -U fde_release --if-exists "$1"',
            "backup-cleanup",
            database,
        )
    return {
        "archive_sha256": digest,
        "restored": restored,
        "status": "verified",
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("create", "verify"))
    parser.add_argument("--project-name", default="cdf-release")
    parser.add_argument("--archive", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        result = (
            create_backup(args.project_name, args.archive)
            if args.action == "create"
            else verify_backup(args.project_name, args.archive)
        )
    except (OSError, ValueError, subprocess.CalledProcessError, json.JSONDecodeError) as error:
        raise SystemExit("Backup action failed without changing the source database.") from error
    print(json.dumps(result, separators=(",", ":"), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
