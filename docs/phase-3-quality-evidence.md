# Evidencia de Fase 3 — Incremento 1: quality gates

Fecha: 18 de julio de 2026.

## Problema y criterios de aceptacion

La Fase 2 ejecutaba formato, lint y pruebas, pero un error de tipos podia llegar a runtime y no
existia una medicion bloqueante ni artifacts descargables para explicar el resultado de CI.

El incremento se acepta cuando:

- Mypy examina aplicacion, pruebas y scripts sin errores.
- Pytest mide branches y lineas del paquete, con minimo global de 75%.
- CI conserva JUnit XML y coverage XML por commit.
- Un cambio que rompa tipos, pruebas o cobertura bloquea el job `quality`.

## Implementacion

- Mypy y pytest-cov se incorporaron al entorno bloqueado por `uv.lock`.
- Los bordes dinamicos de PostgreSQL se tiparon explicitamente sin cambiar su contrato.
- El workflow ejecuta `mypy src tests scripts` antes de migrar y probar.
- Pytest genera `coverage.xml` y `test-results.xml` y aplica `fail_under=75`.
- GitHub Actions sube `quality-evidence-<commit>` durante 14 dias, incluso cuando el job falla.
- Una prueba contractual evita retirar silenciosamente cualquiera de estos gates.

## Evidencia local observada

- Ruff format: 34 archivos aprobados.
- Ruff lint: aprobado.
- Mypy: 29 archivos, cero errores.
- Pytest: 54 pruebas aprobadas contra PostgreSQL efimero.
- Cobertura total con branches: 76.15%; minimo requerido: 75%.
- `coverage.xml` y `test-results.xml`: generados correctamente y excluidos de Git.
- Actionlint y configuracion Compose: aprobados.

## Evidencia remota observada

- Commit: `dbcaedc10a714c2c1f3f28b6aa40fb06b32c46dc`.
- Pipeline: [CI 29638963217](https://github.com/edevelopy/customer-data-foundation/actions/runs/29638963217).
- Jobs `quality`, `container`, `image_changes` y `publish`: aprobados.
- Artifact `quality-evidence-dbcaedc10a714c2c1f3f28b6aa40fb06b32c46dc`: descargado y
  parseado correctamente.
- JUnit remoto: 54 pruebas, cero fallos y cero errores.
- Coverage XML remoto: 78.12% de lineas y 64.89% de ramas; cobertura combinada de pytest
  76.15%, por encima del gate 75%.
- Imagen publicada:
  `ghcr.io/edevelopy/customer-data-foundation-api@sha256:14326b923d71049cea75fc4c942780e092512b4a45c540f85f0f6f229ac2b245`.
- SBOM SHA-256: `54084510f3b212c70a7e74819354fbc4c5a2a5cf0df356e790c69c66cc4eca6e`.

## Limites

El porcentaje global no demuestra por si solo que cada riesgo este cubierto; las pruebas de
integracion, concurrencia, seguridad y contenedor siguen siendo obligatorias. Los artifacts tienen
retencion de 14 dias y no sustituyen evidencia final versionada. La proteccion de `main`, releases,
rollback, secretos administrados y backup/restore permanecen para los siguientes incrementos.
