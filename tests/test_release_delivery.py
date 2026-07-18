from __future__ import annotations

import stat
from argparse import Namespace
from pathlib import Path

import pytest

import fde_foundation.release as release_module
from fde_foundation.database import CURRENT_SCHEMA_REVISION
from fde_foundation.release import (
    REQUIRED_SECRET_FILES,
    deploy,
    load_state,
    rollback,
    validate_release_input,
    validate_runtime_options,
    write_state,
)
from fde_foundation.release_fixture import prepare_fixture

DIGEST_A = "ghcr.io/edevelopy/customer-data-foundation-api@sha256:" + "a" * 64
DIGEST_B = "ghcr.io/edevelopy/customer-data-foundation-api@sha256:" + "b" * 64


def release_args(tmp_path: Path) -> Namespace:
    return Namespace(
        action="deploy",
        api_port=8080,
        audience="fde-release-clients",
        image_ref=DIGEST_B,
        issuer="fde-release",
        partner_failures=1,
        project_name="cdf-release-test",
        secrets_dir=tmp_path / "secrets",
        state_file=tmp_path / "state.json",
        version="v0.3.1",
    )


def test_disposable_fixture_is_private_and_complete(tmp_path: Path) -> None:
    destination = tmp_path / "secrets"

    created = prepare_fixture(destination, issuer="fde-release", audience="fde-clients")

    assert created == sorted(REQUIRED_SECRET_FILES)
    for name in REQUIRED_SECRET_FILES:
        path = destination / name
        assert stat.S_IMODE(path.stat().st_mode) == 0o600
        assert path.read_text(encoding="utf-8")
    with pytest.raises(FileExistsError):
        prepare_fixture(destination, issuer="fde-release", audience="fde-clients")


def test_release_identity_requires_digest_version_and_private_files(tmp_path: Path) -> None:
    destination = tmp_path / "secrets"
    prepare_fixture(destination, issuer="fde-release", audience="fde-clients")

    validate_release_input(DIGEST_A, "v0.3.0", destination)
    with pytest.raises(ValueError):
        validate_release_input(
            "ghcr.io/edevelopy/customer-data-foundation-api:main", "v0.3.0", destination
        )
    with pytest.raises(ValueError):
        validate_release_input(DIGEST_A, "latest", destination)
    (destination / "jwt_secret").chmod(0o644)
    with pytest.raises(ValueError):
        validate_release_input(DIGEST_A, "v0.3.0", destination)


def test_release_state_is_atomic_and_contains_no_secrets(tmp_path: Path) -> None:
    state_file = tmp_path / "state" / "release.json"
    state = {
        "action": "deploy",
        "current": {
            "image_ref": DIGEST_A,
            "schema_revision": CURRENT_SCHEMA_REVISION,
            "version": "v0.3.0",
        },
        "previous": None,
        "project_name": "cdf-release-test",
    }

    write_state(state_file, state)

    assert load_state(state_file) == state
    serialized = state_file.read_text(encoding="utf-8")
    assert "password" not in serialized
    assert "secret" not in serialized


def test_rollback_redeploys_previous_only_when_schema_matches(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    args = release_args(tmp_path)
    current = {
        "image_ref": DIGEST_B,
        "schema_revision": CURRENT_SCHEMA_REVISION,
        "version": "v0.3.1",
    }
    previous = {
        "image_ref": DIGEST_A,
        "schema_revision": CURRENT_SCHEMA_REVISION,
        "version": "v0.3.0",
    }
    write_state(
        args.state_file,
        {
            "action": "deploy",
            "current": current,
            "previous": previous,
            "project_name": args.project_name,
        },
    )
    captured: dict[str, object] = {}

    def fake_deploy(_args, *, image_ref, version, previous, action):
        captured.update(
            image_ref=image_ref,
            version=version,
            previous=previous,
            action=action,
        )
        return {"action": action, "current": {}, "previous": previous}

    monkeypatch.setattr(release_module, "deploy_target", fake_deploy)

    rollback(args)

    assert captured == {
        "action": "rollback",
        "image_ref": DIGEST_A,
        "previous": current,
        "version": "v0.3.0",
    }

    previous["schema_revision"] = "older-schema"
    write_state(
        args.state_file,
        {
            "action": "deploy",
            "current": current,
            "previous": previous,
            "project_name": args.project_name,
        },
    )
    with pytest.raises(ValueError, match="identical schema"):
        rollback(args)


def test_deploy_orders_pull_stack_smoke_then_persists_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    args = release_args(tmp_path)
    prepare_fixture(args.secrets_dir, issuer=args.issuer, audience=args.audience)
    compose_calls: list[tuple[str, ...]] = []
    pull_calls: list[list[str]] = []

    def fake_compose(_args, _environment, *command):
        compose_calls.append(command)

    def fake_run(command, *, check):
        assert check is True
        pull_calls.append(command)

    monkeypatch.setattr(release_module, "compose", fake_compose)
    monkeypatch.setattr(release_module.subprocess, "run", fake_run)

    state = deploy(args)

    assert pull_calls == [["docker", "pull", DIGEST_B]]
    assert compose_calls == [
        ("config", "--quiet"),
        (
            "up",
            "-d",
            "--wait",
            "database",
            "preflight",
            "migrate",
            "api",
            "partner_api",
            "integration_worker",
        ),
        ("--profile", "smoke", "run", "--rm", "release_smoke"),
    ]
    assert state["action"] == "deploy"
    assert state["current"]["image_ref"] == DIGEST_B
    assert state["previous"] is None
    assert load_state(args.state_file) == state


def test_failed_smoke_does_not_advance_release_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    args = release_args(tmp_path)
    prepare_fixture(args.secrets_dir, issuer=args.issuer, audience=args.audience)
    original = {
        "action": "deploy",
        "current": {
            "image_ref": DIGEST_A,
            "schema_revision": CURRENT_SCHEMA_REVISION,
            "version": "v0.3.0",
        },
        "previous": None,
        "project_name": args.project_name,
    }
    write_state(args.state_file, original)

    def fail_on_smoke(_args, _environment, *command):
        if "release_smoke" in command:
            raise release_module.subprocess.CalledProcessError(1, command)

    monkeypatch.setattr(release_module, "compose", fail_on_smoke)
    monkeypatch.setattr(release_module.subprocess, "run", lambda *_args, **_kwargs: None)

    with pytest.raises(release_module.subprocess.CalledProcessError):
        deploy(args)

    assert load_state(args.state_file) == original


def test_release_runtime_options_are_bounded(tmp_path: Path) -> None:
    args = release_args(tmp_path)
    validate_runtime_options(args)

    args.project_name = "INVALID PROJECT"
    with pytest.raises(ValueError, match="project name"):
        validate_runtime_options(args)
    args.project_name = "cdf-release"
    args.api_port = 0
    with pytest.raises(ValueError, match="runtime limits"):
        validate_runtime_options(args)


def test_release_compose_uses_immutable_image_and_file_secrets() -> None:
    project_root = Path(__file__).resolve().parents[1]
    compose = (project_root / "deploy" / "compose.release.yaml").read_text(encoding="utf-8")

    for expected in (
        "${IMAGE_REF:?set immutable IMAGE_REF with sha256 digest}",
        "DATABASE_URL_FILE: /run/secrets/database_url",
        "JWT_SECRET_FILE: /run/secrets/jwt_secret",
        "PARTNER_WEBHOOK_SECRET_FILE: /run/secrets/partner_webhook_secret",
        'command: ["fde-config-check", "api", "worker", "partner"]',
        "condition: service_completed_successfully",
        "internal: true",
        "release_database:",
        "integration_smoke.py",
    ):
        assert expected in compose
    assert "build:" not in compose
    assert "JWT_SECRET:" not in compose
    assert "POSTGRES_PASSWORD:" not in compose
