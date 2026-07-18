from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_runtime_image_is_pinned_and_non_root() -> None:
    dockerfile = (PROJECT_ROOT / "Dockerfile").read_text(encoding="utf-8")

    assert "python:3.12.11-slim-bookworm@sha256:" in dockerfile
    assert "ghcr.io/astral-sh/uv:0.11.16@sha256:" in dockerfile
    assert "USER 10001:10001" in dockerfile
    assert "STOPSIGNAL SIGTERM" in dockerfile
    assert "/health/ready" in dockerfile


def test_compose_enforces_migration_order_and_runtime_hardening() -> None:
    compose = (PROJECT_ROOT / "compose.yaml").read_text(encoding="utf-8")

    for expected in (
        "api_migrate:",
        "condition: service_completed_successfully",
        "read_only: true",
        "no-new-privileges:true",
        "cap_drop:",
        "pids_limit: 128",
        "stop_grace_period: 15s",
    ):
        assert expected in compose


def test_docker_build_context_excludes_local_secrets_and_virtual_environment() -> None:
    dockerignore = (PROJECT_ROOT / ".dockerignore").read_text(encoding="utf-8").splitlines()

    assert ".env" in dockerignore
    assert ".venv" in dockerignore
    assert ".git" in dockerignore
