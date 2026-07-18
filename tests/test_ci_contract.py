from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_ci_enforces_types_coverage_and_downloadable_test_evidence() -> None:
    workflow = (PROJECT_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    project = (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")

    for expected in (
        "uv run mypy src tests scripts",
        "--cov=fde_foundation",
        "--cov-branch",
        "--cov-report=xml:coverage.xml",
        "--junitxml=test-results.xml",
        "quality-evidence-${{ github.sha }}",
        "coverage.xml",
        "test-results.xml",
        "retention-days: 14",
    ):
        assert expected in workflow

    assert "[tool.mypy]" in project
    assert "[tool.coverage.report]" in project
    assert "fail_under = 75" in project
