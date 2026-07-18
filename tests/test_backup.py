from __future__ import annotations

import hashlib
import json
import stat
from pathlib import Path

import pytest

import fde_foundation.backup as backup_module
from fde_foundation.backup import create_backup, verify_backup
from fde_foundation.database import CURRENT_SCHEMA_REVISION

COUNTS: dict[str, int | str] = {
    "import_batches": 1,
    "customers": 1,
    "api_operations": 1,
    "integration_outbox": 1,
    "partner_receipts": 1,
    "schema_revision": CURRENT_SCHEMA_REVISION,
}


def test_backup_is_private_and_manifest_contains_only_safe_counts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    archive = tmp_path / "release.dump"

    def fake_database_command(_container, *_command, stdin=None, stdout=None):
        assert stdin is None
        assert stdout is not None
        stdout.write(b"synthetic-postgresql-archive")

    monkeypatch.setattr(backup_module, "database_command", fake_database_command)
    monkeypatch.setattr(backup_module, "query_counts", lambda _container: COUNTS)

    manifest = create_backup("cdf-release-test", archive)

    assert stat.S_IMODE(archive.stat().st_mode) == 0o600
    assert stat.S_IMODE((tmp_path / "release.dump.json").stat().st_mode) == 0o600
    assert manifest["safe_counts"] == COUNTS
    assert "email" not in json.dumps(manifest)


def test_verification_rejects_tampered_archive_before_restore(tmp_path: Path) -> None:
    archive = tmp_path / "release.dump"
    archive.write_bytes(b"tampered")
    (tmp_path / "release.dump.json").write_text(
        json.dumps(
            {
                "format_version": 1,
                "archive_sha256": hashlib.sha256(b"original").hexdigest(),
                "safe_counts": COUNTS,
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="digest"):
        verify_backup("cdf-release-test", archive)
