"""Despliega o revierte una release inmutable y actualiza estado solo despues del smoke."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final

from fde_foundation.database import CURRENT_SCHEMA_REVISION

IMAGE_PATTERN: Final = re.compile(
    r"^ghcr\.io/edevelopy/customer-data-foundation-api@sha256:[0-9a-f]{64}$"
)
VERSION_PATTERN: Final = re.compile(r"^v\d+\.\d+\.\d+$")
PROJECT_PATTERN: Final = re.compile(r"^[a-z0-9][a-z0-9_-]{0,62}$")
REQUIRED_SECRET_FILES: Final = (
    "postgres_password",
    "database_url",
    "jwt_secret",
    "identifier_hash_key",
    "partner_webhook_secret",
    "operator_token",
)
PROJECT_ROOT: Final = Path(__file__).resolve().parents[2]
COMPOSE_FILE: Final = PROJECT_ROOT / "deploy" / "compose.release.yaml"


def validate_release_input(image_ref: str, version: str, secrets_dir: Path) -> None:
    if not IMAGE_PATTERN.fullmatch(image_ref) or not VERSION_PATTERN.fullmatch(version):
        raise ValueError("invalid immutable release identity")
    resolved_secrets = secrets_dir.resolve(strict=True)
    for name in REQUIRED_SECRET_FILES:
        path = resolved_secrets / name
        if not path.is_file() or path.stat().st_mode & 0o077:
            raise ValueError("release secret files must exist with mode 0600")


def validate_runtime_options(args: argparse.Namespace) -> None:
    if not PROJECT_PATTERN.fullmatch(args.project_name):
        raise ValueError("invalid release project name")
    if not 1 <= args.api_port <= 65535 or not 0 <= args.partner_failures <= 20:
        raise ValueError("invalid release runtime limits")


def load_state(state_file: Path) -> dict[str, Any] | None:
    if not state_file.exists():
        return None
    loaded = json.loads(state_file.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ValueError("release state is invalid")
    return loaded


def write_state(state_file: Path, state: dict[str, Any]) -> None:
    state_file.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{state_file.name}.", dir=state_file.parent, text=True
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as temporary_file:
            json.dump(state, temporary_file, indent=2, sort_keys=True)
            temporary_file.write("\n")
        os.replace(temporary_name, state_file)
    except BaseException:
        Path(temporary_name).unlink(missing_ok=True)
        raise


def release_environment(args: argparse.Namespace, image_ref: str) -> dict[str, str]:
    return {
        **os.environ,
        "DEPLOY_API_PORT": str(args.api_port),
        "DEPLOY_PROJECT_NAME": args.project_name,
        "DEPLOY_SECRETS_DIR": str(args.secrets_dir.resolve()),
        "IMAGE_REF": image_ref,
        "JWT_AUDIENCE": args.audience,
        "JWT_ISSUER": args.issuer,
        "PARTNER_SIMULATED_FAILURES": str(args.partner_failures),
    }


def compose(args: argparse.Namespace, environment: dict[str, str], *command: str) -> None:
    subprocess.run(
        ["docker", "compose", "-f", str(COMPOSE_FILE), *command],
        cwd=PROJECT_ROOT,
        env=environment,
        check=True,
    )


def deploy_target(
    args: argparse.Namespace,
    *,
    image_ref: str,
    version: str,
    previous: dict[str, Any] | None,
    action: str,
) -> dict[str, Any]:
    validate_runtime_options(args)
    validate_release_input(image_ref, version, args.secrets_dir)
    environment = release_environment(args, image_ref)
    compose(args, environment, "config", "--quiet")
    subprocess.run(["docker", "pull", image_ref], check=True)
    compose(
        args,
        environment,
        "up",
        "-d",
        "--wait",
        "database",
        "preflight",
        "migrate",
        "api",
        "partner_api",
        "integration_worker",
    )
    compose(args, environment, "--profile", "smoke", "run", "--rm", "release_smoke")
    current = {
        "deployed_at": datetime.now(UTC).isoformat(),
        "image_ref": image_ref,
        "schema_revision": CURRENT_SCHEMA_REVISION,
        "version": version,
    }
    state = {
        "action": action,
        "current": current,
        "previous": previous,
        "project_name": args.project_name,
    }
    write_state(args.state_file, state)
    return state


def deploy(args: argparse.Namespace) -> dict[str, Any]:
    existing = load_state(args.state_file)
    previous = existing.get("current") if existing else None
    return deploy_target(
        args,
        image_ref=args.image_ref,
        version=args.version,
        previous=previous,
        action="deploy",
    )


def rollback(args: argparse.Namespace) -> dict[str, Any]:
    existing = load_state(args.state_file)
    if not existing or not isinstance(existing.get("previous"), dict):
        raise ValueError("no previous release is available")
    current = existing.get("current")
    previous = existing["previous"]
    if not isinstance(current, dict) or previous.get("schema_revision") != current.get(
        "schema_revision"
    ):
        raise ValueError("automatic rollback requires identical schema revisions")
    return deploy_target(
        args,
        image_ref=str(previous["image_ref"]),
        version=str(previous["version"]),
        previous=current,
        action="rollback",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("deploy", "rollback"))
    parser.add_argument("--image-ref", default="")
    parser.add_argument("--version", default="")
    parser.add_argument("--secrets-dir", type=Path, required=True)
    parser.add_argument("--state-file", type=Path, required=True)
    parser.add_argument("--project-name", default="cdf-release")
    parser.add_argument("--api-port", type=int, default=8080)
    parser.add_argument("--issuer", default="fde-release")
    parser.add_argument("--audience", default="fde-release-clients")
    parser.add_argument("--partner-failures", type=int, default=1)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        state = deploy(args) if args.action == "deploy" else rollback(args)
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        raise SystemExit("Release action failed; persisted state was not advanced.") from error
    print(
        json.dumps(
            {
                "action": state["action"],
                "image_ref": state["current"]["image_ref"],
                "schema_revision": state["current"]["schema_revision"],
                "status": "healthy",
                "version": state["current"]["version"],
            },
            separators=(",", ":"),
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
