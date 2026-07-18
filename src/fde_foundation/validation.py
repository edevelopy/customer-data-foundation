"""Validacion estricta de archivos CSV de clientes."""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Final

EXPECTED_FIELDS: Final = ("email", "first_name", "last_name", "phone", "source")
MAX_FILE_BYTES: Final = 10 * 1024 * 1024
MAX_ROWS: Final = 10_000
EMAIL_PATTERN: Final = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PHONE_PATTERN: Final = re.compile(r"^\+[1-9]\d{7,14}$")


@dataclass(frozen=True)
class ValidationIssue:
    """Error accionable que deliberadamente no contiene el valor recibido."""

    row: int | None
    field: str
    code: str
    message: str
    correction: str


@dataclass(frozen=True)
class ValidatedCustomer:
    """Registro normalizado que solo existe en memoria durante la validacion."""

    email: str
    first_name: str
    last_name: str
    phone: str
    source: str
    row_number: int


@dataclass
class ValidationResult:
    """Resultado del lote completo bajo semantica todo-o-nada."""

    total_rows: int
    valid_rows: int
    issues: list[ValidationIssue]
    records: list[ValidatedCustomer] = field(default_factory=list, repr=False)

    @property
    def accepted(self) -> bool:
        return not self.issues

    def to_report(self) -> dict[str, object]:
        return {
            "accepted": self.accepted,
            "mode": "strict",
            "summary": {
                "total_rows": self.total_rows,
                "valid_rows": self.valid_rows,
                "error_count": len(self.issues),
            },
            "issues": [asdict(issue) for issue in self.issues],
        }


def issue(
    row: int | None,
    field: str,
    code: str,
    message: str,
    correction: str,
) -> ValidationIssue:
    return ValidationIssue(row, field, code, message, correction)


def normalize_text(value: str) -> str:
    return " ".join(value.strip().split())


def validate_email(value: str, row_number: int) -> tuple[str, list[ValidationIssue]]:
    normalized = value.strip().casefold()
    issues: list[ValidationIssue] = []
    if not normalized:
        issues.append(
            issue(row_number, "email", "required", "El email es obligatorio.", "Agrega un email.")
        )
    elif len(normalized) > 254 or not EMAIL_PATTERN.fullmatch(normalized):
        issues.append(
            issue(
                row_number,
                "email",
                "invalid_format",
                "El email no tiene un formato valido.",
                "Usa un formato como nombre@empresa.com.",
            )
        )
    return normalized, issues


def validate_name(value: str, field: str, row_number: int) -> tuple[str, list[ValidationIssue]]:
    normalized = normalize_text(value)
    issues: list[ValidationIssue] = []
    if not normalized:
        issues.append(
            issue(row_number, field, "required", "El nombre es obligatorio.", "Agrega el nombre.")
        )
    elif len(normalized) > 80 or not normalized.isprintable():
        issues.append(
            issue(
                row_number,
                field,
                "invalid_text",
                "El nombre contiene texto no permitido o supera 80 caracteres.",
                "Usa texto visible de hasta 80 caracteres.",
            )
        )
    return normalized, issues


def validate_phone(value: str, row_number: int) -> tuple[str, list[ValidationIssue]]:
    normalized = value.strip()
    if normalized and not PHONE_PATTERN.fullmatch(normalized):
        return normalized, [
            issue(
                row_number,
                "phone",
                "invalid_format",
                "El telefono no tiene formato internacional E.164.",
                "Usa el signo +, codigo de pais y entre 8 y 15 digitos.",
            )
        ]
    return normalized, []


def validate_source(value: str, row_number: int) -> tuple[str, list[ValidationIssue]]:
    normalized = normalize_text(value).casefold()
    if not normalized:
        return normalized, [
            issue(
                row_number, "source", "required", "El origen es obligatorio.", "Agrega el origen."
            )
        ]
    if len(normalized) > 50 or not normalized.isprintable():
        return normalized, [
            issue(
                row_number,
                "source",
                "invalid_text",
                "El origen contiene texto no permitido o supera 50 caracteres.",
                "Usa texto visible de hasta 50 caracteres.",
            )
        ]
    return normalized, []


def validate_headers(fieldnames: list[str] | None) -> list[ValidationIssue]:
    if fieldnames is None:
        return [
            issue(
                None,
                "header",
                "missing",
                "El archivo no tiene encabezado.",
                "Agrega el encabezado requerido.",
            )
        ]

    duplicates = sorted({name for name in fieldnames if fieldnames.count(name) > 1})
    missing = sorted(set(EXPECTED_FIELDS) - set(fieldnames))
    unexpected = sorted(set(fieldnames) - set(EXPECTED_FIELDS))
    issues: list[ValidationIssue] = []
    if duplicates:
        issues.append(
            issue(
                None,
                "header",
                "duplicate_columns",
                "Hay columnas repetidas.",
                f"Conserva una sola columna: {', '.join(duplicates)}.",
            )
        )
    if missing:
        issues.append(
            issue(
                None,
                "header",
                "missing_columns",
                "Faltan columnas obligatorias.",
                f"Agrega: {', '.join(missing)}.",
            )
        )
    if unexpected:
        issues.append(
            issue(
                None,
                "header",
                "unexpected_columns",
                "Existen columnas no autorizadas.",
                f"Elimina: {', '.join(unexpected)}.",
            )
        )
    return issues


def validate_csv(path: Path, *, max_rows: int = MAX_ROWS) -> ValidationResult:
    """Valida un CSV completo sin persistir ningun registro."""
    try:
        file_size = path.stat().st_size
    except OSError:
        return ValidationResult(
            0,
            0,
            [
                issue(
                    None,
                    "file",
                    "unreadable",
                    "No se pudo leer el archivo.",
                    "Comprueba la ruta y los permisos.",
                )
            ],
        )

    if file_size > MAX_FILE_BYTES:
        return ValidationResult(
            0,
            0,
            [
                issue(
                    None,
                    "file",
                    "too_large",
                    "El archivo supera el limite de 10 MiB.",
                    "Divide el archivo en lotes mas pequenos.",
                )
            ],
        )

    issues: list[ValidationIssue] = []
    total_rows = 0
    valid_rows = 0
    seen_emails: dict[str, int] = {}
    validated_records: list[ValidatedCustomer] = []

    try:
        with path.open(encoding="utf-8-sig", newline="") as csv_file:
            reader = csv.DictReader(csv_file)
            header_issues = validate_headers(reader.fieldnames)
            if header_issues:
                return ValidationResult(0, 0, header_issues)

            for row_number, row in enumerate(reader, start=2):
                total_rows += 1
                if total_rows > max_rows:
                    issues.append(
                        issue(
                            None,
                            "file",
                            "too_many_rows",
                            f"El archivo supera el limite de {max_rows} registros.",
                            "Divide el archivo en lotes mas pequenos.",
                        )
                    )
                    break

                row_issues: list[ValidationIssue] = []
                if None in row:
                    row_issues.append(
                        issue(
                            row_number,
                            "row",
                            "extra_values",
                            "La fila contiene valores sin encabezado.",
                            "Elimina los valores adicionales.",
                        )
                    )

                email, email_issues = validate_email(row.get("email", "") or "", row_number)
                first_name, first_name_issues = validate_name(
                    row.get("first_name", "") or "", "first_name", row_number
                )
                last_name, last_name_issues = validate_name(
                    row.get("last_name", "") or "", "last_name", row_number
                )
                phone, phone_issues = validate_phone(row.get("phone", "") or "", row_number)
                source, source_issues = validate_source(row.get("source", "") or "", row_number)
                row_issues.extend(
                    email_issues
                    + first_name_issues
                    + last_name_issues
                    + phone_issues
                    + source_issues
                )

                if not email_issues:
                    if email in seen_emails:
                        row_issues.append(
                            issue(
                                row_number,
                                "email",
                                "duplicate_in_file",
                                "El email esta repetido en el archivo.",
                                "Conserva una sola fila; la primera aparece en la fila "
                                f"{seen_emails[email]}.",
                            )
                        )
                    else:
                        seen_emails[email] = row_number

                if row_issues:
                    issues.extend(row_issues)
                else:
                    validated_records.append(
                        ValidatedCustomer(email, first_name, last_name, phone, source, row_number)
                    )
                    valid_rows += 1
    except UnicodeDecodeError:
        issues.append(
            issue(
                None,
                "file",
                "invalid_encoding",
                "El archivo no usa UTF-8.",
                "Exporta el CSV con codificacion UTF-8.",
            )
        )
    except csv.Error:
        issues.append(
            issue(
                None,
                "file",
                "malformed_csv",
                "El contenido CSV esta mal formado.",
                "Revisa comillas y separadores.",
            )
        )

    return ValidationResult(
        total_rows,
        valid_rows,
        issues,
        records=validated_records if not issues else [],
    )


def write_json_report(report: dict[str, object], destination: Path) -> None:
    """Escribe un reporte JSON de forma atomica."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    file_descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.", dir=destination.parent, text=True
    )
    try:
        with os.fdopen(file_descriptor, "w", encoding="utf-8") as temporary_file:
            temporary_file.write(payload)
        os.replace(temporary_name, destination)
    except BaseException:
        Path(temporary_name).unlink(missing_ok=True)
        raise


def write_report(result: ValidationResult, destination: Path) -> None:
    """Escribe el reporte de validacion sin incluir registros normalizados."""
    write_json_report(result.to_report(), destination)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv_file", type=Path, help="archivo CSV que se validara")
    parser.add_argument("--report", type=Path, help="ruta opcional para el reporte JSON")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = validate_csv(args.csv_file)
    if args.report:
        write_report(result, args.report)
    summary = result.to_report()["summary"]
    print(
        f"accepted={str(result.accepted).lower()} "
        f"rows={summary['total_rows']} errors={summary['error_count']}"
    )
    return int(not result.accepted)


if __name__ == "__main__":
    raise SystemExit(main())
