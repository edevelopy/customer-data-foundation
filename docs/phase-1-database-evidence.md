# Evidencia de Fase 1 — PostgreSQL e idempotencia

Fecha de verificacion: 18 de julio de 2026.

## Decision implementada

Una reimportacion identica es idempotente. Un email existente con datos diferentes rechaza
y revierte el lote completo. Un email existente con los mismos datos puede participar en
otro lote sin crear un cliente duplicado.

## Entorno observado

- PostgreSQL 18.4 mediante la imagen oficial `postgres:18.4-alpine`.
- Contenedor saludable y puerto publicado solamente en `127.0.0.1:55433`.
- Esquema creado con restricciones para normalizacion, longitudes y telefono E.164.
- Credenciales locales cargadas desde `.env`, excluido de Git.

## Verificacion observada

| Escenario | Resultado |
|---|---|
| Primera importacion valida | 3 insertados, codigo 0 |
| Repeticion exacta | `already_imported`, 0 insertados, codigo 0 |
| Cliente existente con datos diferentes | `conflict`, codigo 1 |
| Lote con cliente nuevo y otro en conflicto | Cliente nuevo ausente despues del rollback |
| Dos importaciones exactas concurrentes | Un lote y dos clientes, sin duplicados |
| Cliente identico en archivo con bytes diferentes | 0 insertados, 1 existente |
| Archivo invalido con URL de base inalcanzable | Rechazado antes de intentar conectar |
| Fallo de conexion | Reporte generico sin usuario, contrasena o URL |
| Suite local con PostgreSQL real | 16 pruebas aprobadas |
| Clon nuevo, base separada e importacion | Aprobado con 16 pruebas |
| GitHub Actions con PostgreSQL efimero | Aprobado |
| Ruff | Formato y linting aprobados |

Despues de la demostracion manual, PostgreSQL contenia cuatro clientes y dos lotes. El
cliente nuevo del archivo conflictivo tenia conteo cero, confirmando el rollback.

Pipeline observado:
<https://github.com/edevelopy/customer-data-foundation/actions/runs/29630299194>

## Incidente controlado durante la preparacion

El puerto inicialmente propuesto ya pertenecia a otro contenedor. No se detuvo ni modifico
el proyecto ajeno; este repositorio se movio al puerto libre 55433. Docker Desktop tambien
demoro una descarga por su gestor de credenciales, por lo que se uso la misma imagen 18.4
ya disponible localmente y CI queda como verificacion independiente de descarga.

## Riesgos y trabajo pendiente

- El esquema inicial usa `CREATE TABLE IF NOT EXISTS`; falta una herramienta versionada de migraciones.
- El email continua siendo una identidad provisional del piloto.
- Los intentos invalidados o revertidos solo producen un reporte y no se guardan como auditoria.
- Aun faltan metricas operativas, logs estructurados y la demo final de la Fase 1.
- No existen backups porque esta base contiene solamente datos sinteticos locales.
