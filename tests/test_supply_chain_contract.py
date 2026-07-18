from __future__ import annotations

import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = PROJECT_ROOT / ".github" / "workflows" / "ci.yml"


def test_publish_is_limited_to_main_after_quality_gates() -> None:
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")

    assert "github.event_name == 'push' && github.ref == 'refs/heads/main'" in workflow
    assert "needs: [image_changes, quality, container]" in workflow
    assert "needs.image_changes.outputs.publish == 'true'" in workflow
    assert "packages: write" in workflow
    assert "id-token: write" in workflow
    assert "attestations: write" in workflow


def test_image_contract_uses_digest_sbom_provenance_and_vulnerability_gate() -> None:
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")

    for expected in (
        "type=sha,prefix=sha-,format=long",
        "type=raw,value=main",
        "provenance: mode=max",
        "sbom: true",
        "ignore-unfixed: true",
        "severity: HIGH,CRITICAL",
        "sbom.spdx.json",
        "gh attestation verify",
        "--predicate-type https://slsa.dev/provenance/v1",
        "--predicate-type https://spdx.dev/Document",
    ):
        assert expected in workflow


def test_all_external_actions_are_pinned_to_commits() -> None:
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
    external_uses = re.findall(r"^\s*uses:\s*([^\s]+)", workflow, flags=re.MULTILINE)

    assert external_uses
    assert all(re.fullmatch(r"[^@]+@[0-9a-f]{40}", item) for item in external_uses)
