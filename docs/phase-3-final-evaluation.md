# Evaluacion Final — Fase 3: entrega reproducible y automatizacion

Fecha: 18 de julio de 2026.

## Decision

**APROBADO — 37/40.**

Umbral: al menos 32/40, ningun criterio critico en cero y evidencia observada para deploy,
restauracion, rollback, cadena de suministro y proteccion de `main`. El resultado evalua esta fase;
no certifica produccion, cumplimiento normativo, alta disponibilidad ni valor validado con usuarios.

## Rubrica

Escala: 0 ausente, 1 demostracion fragil, 2 parcial, 3 solido con limites, 4 defendible y repetible.

| Criterio | Puntos | Evidencia y juicio |
|---|---:|---|
| Entrega reproducible | 4 | Clon limpio, lock, Compose, imagen por digest y deploy de un comando |
| CI y proteccion de cambios | 4 | Lint, tipos, 74 tests, cobertura, contenedor y PR defectuosa bloqueada |
| Configuracion y secretos | 3 | Siete archivos `_FILE`, preflight y fallos seguros; sin gestor cloud/rotacion dual |
| Versionado, release y rollback | 4 | `v0.3.0`/`v0.3.1`, promocion sin rebuild, estado atomico y rollback real |
| Observabilidad y alertas | 3 | Health, JSON, metricas autenticadas y reglas; sin canal/SLO acordado con cliente |
| Backup y restauracion | 3 | Dump `0600`, hash y restore aislado probado; sin cifrado externo ni RPO/RTO contractual |
| Seguridad de runtime | 4 | No-root, read-only, cap drop, red interna, edge local y secretos no expuestos |
| Cadena de suministro | 4 | Trivy, SBOM, SLSA/SPDX attestations y vulnerabilidad deliberada bloqueada |
| Fallos y recuperacion | 4 | Migracion fallida, DB inalcanzable, partner `503`, alerta, restore y rollback |
| Comunicacion y adopcion | 4 | Contratos, runbooks, evidencia, guion no tecnico y limites explicitos |
| **Total** | **37/40** | **Aprobado** |

## Examen final observado

- `main` limpio en commit `78475a8`; CI remota `29640444907` aprobada.
- Release `v0.3.1` promovio el digest probado y su workflow `29640574808` aprobo.
- `v0.3.1` se desplego sobre el volumen de `v0.3.0`; health, puerto host y metricas aprobaron.
- Rollback real a `v0.3.0`: imagen anterior activa, esquema vigente y conteos preservados.
- Roll-forward real dejo `v0.3.1` activo, cuatro operaciones/entregas y cero dead letters.
- Backup SHA-256 `c9848202…a63a31a9` se restauro con esquema y conteos coincidentes.
- Trivy rechazo siete vulnerabilidades HIGH en un fixture aislado.
- La PR defectuosa #1 quedo bloqueada y cerrada sin merge.
- Otro clon limpio instalo, probo y desplego la release; su stack temporal fue eliminado.

## Limites que deben decirse ante un cliente

- Docker Compose prueba el contrato, no ofrece alta disponibilidad ni orquestacion cloud.
- El JWT compartido del piloto debe reemplazarse por IdP/OIDC, TLS, rate limiting y politicas reales.
- El partner comparte PostgreSQL solo como simulador; una integracion real posee datos y credenciales.
- Alertas no tienen todavia propietario, canal ni SLO aprobado.
- Backups no tienen almacenamiento cifrado externo, retencion, RPO/RTO ni prueba multi-host.
- Dependabot no esta habilitado; el escaneo bloquea cambios, pero la actualizacion no es automatica.
- El caso de negocio y ahorro siguen pendientes de validacion con una persona usuaria real.

## Resultado defendible

La Fase 3 demuestra que el agente puede convertir una aplicacion funcional en una entrega operable:
un cambio defectuoso se bloquea, una release se identifica, una falla se observa, un backup se
restaura y una version se revierte. La aprobacion permite avanzar; no elimina los limites anteriores.

## Que sigue

**Fase 4 — Inteligencia artificial aplicada y verificable:** construir un asistente RAG con fuentes,
permisos, rechazo sin evidencia, evaluaciones reproducibles y una accion simulada que exija
aprobacion humana. La operacion cloud y la adopcion real siguen siendo brechas validas, pero no son el
nombre ni el entregable definido para esta fase de la ruta.
