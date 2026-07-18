from __future__ import annotations

from pathlib import Path

import pytest

from fde_foundation.config_check import validate_targets
from fde_foundation.settings import ConfigurationError, Settings, read_secret

SECRET = "managed-secret-with-more-than-thirty-two-characters"


def api_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://database.example/fde")
    monkeypatch.setenv("JWT_ISSUER", "fde-test")
    monkeypatch.setenv("JWT_AUDIENCE", "fde-clients")


def test_secret_can_be_loaded_from_read_only_style_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    secret_file = tmp_path / "jwt"
    secret_file.write_text(f"{SECRET}\n", encoding="utf-8")
    monkeypatch.delenv("JWT_SECRET", raising=False)
    monkeypatch.setenv("JWT_SECRET_FILE", str(secret_file))

    assert read_secret("JWT_SECRET") == SECRET


def test_secret_rejects_ambiguous_and_multiline_sources(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    secret_file = tmp_path / "jwt"
    secret_file.write_text(f"{SECRET}\nsecond-line", encoding="utf-8")
    monkeypatch.setenv("JWT_SECRET", SECRET)
    monkeypatch.setenv("JWT_SECRET_FILE", str(secret_file))
    with pytest.raises(ConfigurationError):
        read_secret("JWT_SECRET")

    monkeypatch.delenv("JWT_SECRET")
    with pytest.raises(ConfigurationError):
        read_secret("JWT_SECRET")


def test_api_settings_and_preflight_do_not_expose_file_secrets(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    api_environment(monkeypatch)
    for name in ("JWT_SECRET", "IDENTIFIER_HASH_KEY"):
        secret_file = tmp_path / name.casefold()
        secret_file.write_text(SECRET, encoding="utf-8")
        monkeypatch.delenv(name, raising=False)
        monkeypatch.setenv(f"{name}_FILE", str(secret_file))

    settings = Settings.from_environment()
    result = validate_targets(["api"])

    assert settings.jwt_secret == SECRET
    assert settings.identifier_hash_key == SECRET
    assert result == {"status": "ready", "targets": ["api"]}
    assert SECRET not in str(result)


def test_preflight_returns_only_safe_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    api_environment(monkeypatch)
    monkeypatch.setenv("JWT_SECRET", "too-short")
    monkeypatch.setenv("IDENTIFIER_HASH_KEY", SECRET)

    result = validate_targets(["api"])

    assert result == {
        "code": "configuration_invalid",
        "status": "invalid",
        "targets": ["api"],
    }
    assert "too-short" not in str(result)


def test_repository_does_not_track_secret_material() -> None:
    project_root = Path(__file__).resolve().parents[1]
    secret_files = list((project_root / "deploy" / "secrets").iterdir())
    gitignore = (project_root / ".gitignore").read_text(encoding="utf-8")

    assert secret_files == [project_root / "deploy" / "secrets" / "README.md"]
    assert "deploy/secrets/*" in gitignore
