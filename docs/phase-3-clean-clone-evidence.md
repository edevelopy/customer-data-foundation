# Evidencia de Fase 3 — Entrega desde clon limpio

Fecha: 18 de julio de 2026.

## Objetivo

Demostrar que la entrega no depende del directorio, imagen local, archivo `.env` ni base de datos de
desarrollo del autor. El examen parte exclusivamente de `main` remoto y del digest publicado.

## Ejecucion observada

1. Se clono `main` en un directorio temporal nuevo y se comprobo HEAD
   `78475a8c9b34ae8ba1ef5b4c85edb1ddcc6beb62`.
2. `uv sync --locked --all-groups` instalo el lock sin resolver versiones nuevas.
3. Ruff aprobo formato/lint y Mypy aprobo 38 archivos.
4. Las 74 pruebas aprobaron con 75.04% de cobertura combinada.
5. `docker build --check .` termino sin warnings.
6. `fde-release-fixture` creo siete archivos privados descartables.
7. Un unico `fde-release deploy` levanto desde el clon la release `v0.3.1` por digest
   `sha256:e4facaf18a44214aa7ab9f8ad81976ad56198ca2ed5b0a440695ac666a7a2b53`.
8. PostgreSQL, preflight, migracion, API, partner y worker quedaron saludables. El smoke produjo un
   `503`, reintento y termino `delivered` con `attempt_count=2`.
9. `127.0.0.1:58082/health/ready` respondio `ready`; metricas reportaron una importacion, una
   entrega y cero dead letters. El worktree permanecio limpio.
10. Se eliminaron solo los contenedores, redes y volumen del proyecto temporal `cdf-clean-v031`.

## Decision

El criterio de entrega desde clon limpio queda aprobado. Los secretos eran sinteticos y se usaron
solo para el examen; no representan un gestor de secretos de cliente ni autorizan copiar el fixture
a un ambiente compartido.
