# Auditoria de equivalencias — Fase 3

Fecha: 18 de julio de 2026.

## Regla de evaluacion

Una capacidad cuenta como cubierta solo si existe implementacion y evidencia reproducible. Haber
usado una herramienta no demuestra por si solo que el requisito de la fase este completo. Los
cursos se mantienen separados: este documento audita el proyecto, no certifica estudio teorico.

## Cobertura encontrada

| Requisito de la ruta | Estado inicial | Evidencia o brecha |
|---|---|---|
| Dockerfile multi-stage | Cubierto | Builder separado, dependencias bloqueadas y runtime minimo |
| Imagen segura y reproducible | Cubierto | Bases por digest, usuario `10001`, read-only, SBOM, provenance y Trivy |
| Docker Compose | Cubierto | PostgreSQL, migracion, API, partner, worker y clientes smoke |
| FastAPI y PostgreSQL juntos | Cubierto | Orden por health y migracion; smoke desde otro contenedor |
| Health checks no-root | Cubierto | Readiness real, `cap_drop=ALL` y apagado observado |
| Configuracion sin secretos en Git | Cubierto parcialmente | `.env` ignorado y secretos fuera de imagen; falta contrato para gestor externo y rotacion |
| GitHub Actions | Cubierto | Jobs independientes de calidad, contenedor y publicacion |
| Lint, format y tests | Cubierto | Ejecutados en cada push y pull request |
| Type checking | Brecha | Mypy no se ejecutaba antes de esta auditoria |
| Build y analisis Docker | Cubierto | Build check, Trivy local/remoto y smoke del artefacto |
| Cobertura y artefactos de pruebas | Brecha | No habia umbral, XML de cobertura ni JUnit descargable |
| Migraciones seguras | Cubierto parcialmente | Migrador separado y fallo bloqueante; falta integrarlo al release/rollback probado |
| Proteccion de `main` | Brecha confirmada | GitHub reporto `protected=false` y cero rulesets |
| Estrategia de releases | Brecha | Imagen por commit existe, pero no hay version SemVer, release ni promocion controlada |
| Entrega con un comando | Cubierto parcialmente | Compose levanta el stack, pero falta comando de despliegue con preflight y rollback |
| Migracion rota y recuperada | Cubierto | Simulacro observado en la evidencia de contenedores de Fase 2 |
| Dependencia vulnerable detectada | Cubierto parcialmente | Gate Trivy existe; falta un simulacro aislado que pruebe que bloquea |
| Backup y restauracion | Brecha | No existe procedimiento ni prueba de igualdad restaurada |
| Release y rollback | Brecha | No existe release versionada ni reversion observada |

## Incrementos necesarios

1. **Quality gates:** type checking, cobertura minima y artifacts JUnit/coverage.
2. **Configuracion y secretos:** contrato de runtime, archivos de secretos, preflight y rotacion
   sin incorporar valores al repositorio o imagen.
3. **Deploy/release/rollback:** ambiente reproducible, version SemVer, manifiesto de release,
   migracion controlada, smoke y rollback por digest.
4. **Operacion:** metricas y alertas accionables, backup, restauracion y simulacros de fallos.
5. **Gobierno y cierre:** ruleset de `main`, clon limpio, release real, entrega al cliente y
   evaluacion final.

## Criterio de salida

La Fase 3 no se aprobara por reutilizar evidencia de la Fase 2. Debe demostrar que un cambio
defectuoso queda bloqueado, que un release tiene identidad y evidencia, y que datos y servicio
pueden recuperarse mediante procedimientos ejecutados, no supuestos.
