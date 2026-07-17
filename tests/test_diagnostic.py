from pathlib import Path

from fde_foundation.diagnostic import (
    REQUIRED_FILES,
    Check,
    check_project_files,
    render_text,
)


def test_project_files_pass_when_structure_is_complete(tmp_path: Path) -> None:
    for filename in REQUIRED_FILES:
        (tmp_path / filename).touch()

    result = check_project_files(tmp_path)

    assert result.status == "PASS"


def test_project_files_report_every_missing_file(tmp_path: Path) -> None:
    result = check_project_files(tmp_path)

    assert result.status == "FAIL"
    assert all(filename in result.detail for filename in REQUIRED_FILES)


def test_render_text_summarizes_failures_and_warnings() -> None:
    checks = [
        Check("obligatorio", "FAIL", "ausente"),
        Check("opcional", "WARN", "ausente", required=False),
        Check("correcto", "PASS", "listo"),
    ]

    report = render_text(checks)

    assert "1 fallo(s) obligatorio(s)" in report
    assert "1 advertencia(s)" in report
