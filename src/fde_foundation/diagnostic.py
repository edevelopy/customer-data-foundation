"""Diagnostico local, seguro y reproducible para la Fase 0."""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import socket
import ssl
import subprocess
import sys
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Final

MINIMUM_PYTHON: Final = (3, 12)
REQUIRED_FILES: Final = (
    "README.md",
    "pyproject.toml",
    ".gitignore",
    ".env.example",
)


@dataclass(frozen=True)
class Check:
    """Resultado de una comprobacion sin incluir datos sensibles."""

    name: str
    status: str
    detail: str
    required: bool = True


def check_python() -> Check:
    """Comprueba que Python cumpla la version minima del proyecto."""
    current = sys.version_info[:3]
    supported = current >= MINIMUM_PYTHON
    minimum = ".".join(map(str, MINIMUM_PYTHON))
    version = ".".join(map(str, current))
    return Check(
        name="Python",
        status="PASS" if supported else "FAIL",
        detail=f"{version}; minimo requerido: {minimum}",
    )


def check_command(command: str, *, required: bool) -> Check:
    """Comprueba si un comando esta disponible sin ejecutarlo."""
    location = shutil.which(command)
    return Check(
        name=f"Comando {command}",
        status="PASS" if location else ("FAIL" if required else "WARN"),
        detail=location or "no encontrado en PATH",
        required=required,
    )


def check_project_files(project_root: Path) -> Check:
    """Comprueba los archivos minimos del repositorio plantilla."""
    missing = [name for name in REQUIRED_FILES if not (project_root / name).is_file()]
    return Check(
        name="Archivos del proyecto",
        status="FAIL" if missing else "PASS",
        detail=f"faltan: {', '.join(missing)}" if missing else "estructura minima completa",
    )


def check_env_is_ignored(project_root: Path) -> Check:
    """Verifica que Git ignore .env sin leer su contenido."""
    try:
        result = subprocess.run(
            ["git", "check-ignore", "-q", ".env"],
            cwd=project_root,
            check=False,
            capture_output=True,
            timeout=3,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return Check("Proteccion de .env", "FAIL", "no se pudo consultar Git")

    ignored = result.returncode == 0
    return Check(
        name="Proteccion de .env",
        status="PASS" if ignored else "FAIL",
        detail=".env esta ignorado por Git" if ignored else ".env podria incluirse en Git",
    )


def check_temp_write() -> Check:
    """Comprueba escritura temporal y elimina el archivo inmediatamente."""
    try:
        with tempfile.NamedTemporaryFile(prefix="fde-diagnostic-") as temporary_file:
            temporary_file.write(b"ok")
            temporary_file.flush()
    except OSError as error:
        return Check("Escritura temporal", "FAIL", type(error).__name__)
    return Check("Escritura temporal", "PASS", "crear, escribir y eliminar funciona")


def check_dns() -> Check:
    """Comprueba resolucion DNS; es informativa para permitir trabajo sin conexion."""
    try:
        addresses = socket.getaddrinfo("example.com", 443, type=socket.SOCK_STREAM)
    except OSError as error:
        return Check("DNS", "WARN", type(error).__name__, required=False)
    return Check("DNS", "PASS", f"example.com resolvio {len(addresses)} direccion(es)", False)


def check_tls() -> Check:
    """Negocia TLS sin enviar datos de aplicacion; no bloquea el trabajo sin conexion."""
    try:
        context = ssl.create_default_context()
        with (
            socket.create_connection(("example.com", 443), timeout=3) as connection,
            context.wrap_socket(connection, server_hostname="example.com") as secure,
        ):
            version = secure.version() or "version desconocida"
    except (OSError, ssl.SSLError) as error:
        return Check("TLS", "WARN", type(error).__name__, required=False)
    return Check("TLS", "PASS", f"negociacion segura: {version}", required=False)


def check_local_port(port: int = 8000) -> Check:
    """Comprueba si un puerto de desarrollo puede reservarse sin dejarlo abierto."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
            server.bind(("127.0.0.1", port))
    except OSError:
        return Check(f"Puerto local {port}", "WARN", "esta ocupado", required=False)
    return Check(f"Puerto local {port}", "PASS", "disponible", required=False)


def run_checks(project_root: Path) -> list[Check]:
    """Ejecuta todas las comprobaciones en orden estable."""
    return [
        check_python(),
        check_command("git", required=True),
        check_command("docker", required=False),
        check_project_files(project_root),
        check_env_is_ignored(project_root),
        check_temp_write(),
        check_dns(),
        check_tls(),
        check_local_port(),
    ]


def render_text(checks: list[Check]) -> str:
    """Genera un reporte legible sin exponer variables de entorno."""
    lines = [
        "Diagnostico FDE - Fase 0",
        f"Sistema: {platform.system()} {platform.machine()}",
    ]
    lines.extend(f"[{check.status:<4}] {check.name}: {check.detail}" for check in checks)
    failures = sum(check.status == "FAIL" and check.required for check in checks)
    warnings = sum(check.status == "WARN" for check in checks)
    lines.append(f"Resultado: {failures} fallo(s) obligatorio(s), {warnings} advertencia(s)")
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="imprime un reporte JSON")
    return parser.parse_args()


def main() -> int:
    """Punto de entrada de la linea de comandos."""
    args = parse_args()
    project_root = Path(os.environ.get("FDE_PROJECT_ROOT", Path.cwd())).resolve()
    checks = run_checks(project_root)

    if args.json:
        print(json.dumps([asdict(check) for check in checks], indent=2))
    else:
        print(render_text(checks))

    return int(any(check.status == "FAIL" and check.required for check in checks))


if __name__ == "__main__":
    raise SystemExit(main())
