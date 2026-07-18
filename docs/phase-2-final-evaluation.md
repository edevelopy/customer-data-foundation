# Evaluacion final de la Fase 2

Fecha: 18 de julio de 2026.

## Resultado

**Aprobada: 35/40 y ninguna dimension por debajo de 3.**

El proyecto cumple el criterio central de la fase: mantiene consistencia ante reintentos y fallos
simulados, aplica permisos por rol y permite explicar cada importacion y entrega externa sin
consultar PII. La aprobacion corresponde al proyecto de portafolio y a su alcance local; no afirma
que sea un despliegue productivo ni que los cursos de la ruta hayan sido completados.

## Explicacion para un cliente no tecnico

Un sistema autorizado entrega el archivo y recibe un resultado verificable. Si el sistema socio
esta caido, la importacion confirmada no se pierde ni cambia de resultado: queda una notificacion
durable, se reintenta con el mismo identificador y el socio elimina duplicados. Operaciones puede
ver que paso, cuantos intentos hubo y si hace falta intervenir, sin abrir datos personales.

## Rubrica

| Dimension | Puntuacion | Evidencia y limite |
|---|---:|---|
| Problema y valor | 3 | Personas, flujo, resultado y metricas definidos; caso y ahorro aun no validados con usuario real |
| Funcionalidad | 4 | Importacion, consulta, permisos, recuperacion, integracion y fallos parciales observados |
| Calidad tecnica | 4 | Limites claros, migraciones, outbox, worker, contratos estrictos y decisiones arquitectonicas |
| Datos e integraciones | 4 | Transacciones, idempotencia, HMAC, leases, fencing, deduplicacion y at-least-once |
| Testing | 4 | 53 pruebas unitarias, de endpoint, contrato, PostgreSQL, concurrencia y contenedor |
| Seguridad | 3 | PII minimizada, JWT, roles, secretos externos, no-root, read-only, SBOM y escaneo; sin IdP/TLS/WAF |
| Operacion | 3 | Health, estados, codigos seguros, backoff, dead letter, runbook y apagado limpio; sin alertas ni backups |
| Comunicacion | 4 | Descubrimiento, OpenAPI, diagramas, ADR, contratos, evidencia y demos para audiencia tecnica y negocio |
| Experiencia de usuario | 3 | API versionada, errores accionables y demo reproducible; sin UI ni prueba de usabilidad real |
| Entrega y adopcion | 3 | Clon limpio, Compose, CI, imagen por digest y guia de consumo; sin cloud ni capacitacion con cliente |
| **Total** | **35/40** | **Supera el minimo de 30/40 y todas las dimensiones superan 2** |

## Criterio de aprobacion de la ruta

| Criterio | Resultado | Evidencia |
|---|---|---|
| Consistencia ante reintentos | Aprobado | Misma clave y body devuelven la operacion original; reutilizacion conflictiva produce `409` |
| Consistencia ante fallos simulados | Aprobado | Outbox en la transaccion del resultado; `503` conserva la importacion y entrega en intento 2 |
| Permisos correctos | Aprobado | Operador escribe y lee lo propio; auditor solo lee; otro operador recibe `404` |
| Diagnostico de integraciones | Aprobado | `operation_id`, `event_id`, estado, intento, duracion y codigo seguro sin payload ni PII |

## Requisitos del proyecto

- FastAPI, PostgreSQL, migraciones, JWT, roles y estado operacional persistido.
- Webhook HMAC con timestamp, comparacion constante y ventana anti-replay.
- Timeout, backoff exponencial, presupuesto de reintentos y dead letter.
- Idempotencia del request, del evento y del receptor; entrega at-least-once sin prometer
  exactly-once.
- Sincronizacion incremental dentro del alcance aprobado: una notificacion tecnica por operacion
  aceptada. No replica perfiles ni funciona como reconciliador general.
- Fallo parcial recuperable: la disponibilidad del socio no modifica la importacion confirmada.
- Pruebas de contrato para payload, headers, firma, replay, identidad y respuestas.

## Artefactos FDE

- [Descubrimiento y flujo actual/deseado](integration-discovery.md).
- [OpenAPI 3.1 versionado](openapi.json), protegido contra drift con una prueba automatizada.
- [Arquitectura, dos secuencias y ADR](integration-architecture.md).
- [Riesgos, dependencias y fuera de alcance](integration-architecture.md#riesgos-vigentes).
- [Contrato HTTP](api-contract.md) y [contrato de integracion](integration-contract.md).
- [Runbook operacional](runbook.md) y [demo de recuperacion](integration-demo-script.md).

## Verificacion final observada

Se clono `main` en un directorio temporal aislado en el commit
`a9f251d793ba9059db805597fc9d5db12024fad8`. Desde ese clon:

- `uv sync --locked --all-groups` reconstruyo el entorno sin dependencias manuales.
- Formato y lint aprobaron.
- La especificacion OpenAPI exportada fue identica a `/openapi.json` del proceso real.
- 53 pruebas aprobaron contra PostgreSQL efimero.
- API, partner y worker arrancaron despues de `0004_integration_outbox`.
- Los tres procesos ejecutaron con UID `10001`, root filesystem read-only y `cap_drop=ALL`.
- Un smoke externo importo correctamente y otro observo `partner_http_503` seguido de
  `status=delivered` en el intento 2.
- Los logs de los tres servicios no contenian los emails ni telefonos sinteticos enviados.
- API, partner y worker terminaron con codigo `0` dentro de 15 segundos.
- Contenedores, red y volumen de evaluacion fueron eliminados; el clon se movio a la Papelera.

Pipeline del commit examinado:
[CI 29636026903](https://github.com/edevelopy/customer-data-foundation/actions/runs/29636026903).
Los jobs `quality`, `container`, `image_changes` y `publish` aprobaron.

Artefacto examinado:

- Imagen: `ghcr.io/edevelopy/customer-data-foundation-api@sha256:949e12a5ff938cb211e06b6fe58000783c024f89f3a3d8856cd54c105905ed95`.
- Plataformas: `linux/amd64` y `linux/arm64`.
- Pull anonimo por digest: aprobado; runtime `10001:10001`.
- Trivy: cero vulnerabilidades corregibles `HIGH` o `CRITICAL`.
- SBOM SPDX 2.3: 137 paquetes; SHA-256
  `cfda6fa1c2a0256a1a12c7841646efa7c3e3f18ecd36acd94b34e33c4aef9688`.
- Attestations SLSA provenance y SPDX verificadas contra el workflow firmante.

## Cierre formal publicado

La evaluacion se publico en el commit
`062ae453fccf2a2a712502c17c390119b2dcc12c`. El pipeline de cierre
[CI 29636201709](https://github.com/edevelopy/customer-data-foundation/actions/runs/29636201709)
repitio las 53 pruebas, el stack, el fallo parcial, el escaneo y la publicacion.

Artefacto final de la Fase 2:

- Imagen: `ghcr.io/edevelopy/customer-data-foundation-api@sha256:cedaf9de84d5e0eec54358d299f88e64bd18f21e5bce8a926e91ef5033f971e6`.
- Plataformas: `linux/amd64` y `linux/arm64`.
- Pull anonimo y runtime `10001:10001`: aprobados desde una configuracion Docker vacia.
- SBOM SPDX 2.3: 137 paquetes; SHA-256
  `028b6709f19215bffbd3e47e063c2c9df7ef9855d116755528ac872fc9e4495f`.
- Provenance SLSA y attestation SPDX: verificadas para ese mismo digest.

## Brecha encontrada y corregida durante la evaluacion

FastAPI ya publicaba OpenAPI en runtime, pero el repositorio no conservaba una copia versionada.
Se agregaron `docs/openapi.json`, un exportador determinista y una prueba de igualdad con el
contrato real. La evaluacion se repitio despues de la correccion y aprobo.

## Limites y deuda aceptada

- JWT usa un secreto compartido local; produccion necesita OIDC/OAuth 2.0, claves asimetricas,
  rotacion, TLS, gateway y rate limiting.
- La persistencia usa SQL explicito con psycopg, no ORM. Es una decision valida para este piloto,
  pero no demuestra el punto curricular de practicar un ORM.
- No hay circuit breaker, cache, limite/alerta de backlog, replay administrado ni reconciliacion
  completa. El outbox y backoff reducen el acoplamiento, pero no sustituyen esos controles.
- El socio simulado comparte PostgreSQL por conveniencia local. Un socio real posee sus propias
  credenciales, receipts, retencion y backups.
- No existen despliegue cloud, alta disponibilidad, restauracion probada, metricas exportadas,
  alertas ni SLO.
- La auditoria es operacional, no un ledger inmutable de cumplimiento.
- No se procesan CSV de forma asincrona y no hay cancelacion, paginacion ni filtros porque el
  alcance no expone colecciones ni trabajos largos.
- No hubo usuario real, datos reales, capacitacion ni medicion posterior de adopcion.

## Limite de la aprobacion educativa

Esta evaluacion aprueba el **proyecto de la Fase 2**. No marca como completados los cursos de
FastAPI, SOLID, patrones, OAuth/OIDC ni cada tema teorico de la ruta. Esos elementos requieren
estudio o evidencia separada. Tampoco se atribuyen puntos por afirmar funcionalidades fuera del
alcance.

## Siguiente fase recomendada

Iniciar la **Fase 3 — Entrega reproducible y automatizacion** con una auditoria de equivalencias:
Docker, Compose, CI, escaneo y publicacion ya tienen evidencia avanzada, por lo que no deben
rehacerse. El trabajo nuevo debe concentrarse en los huecos de entrega: ambiente desplegado,
configuracion y secretos administrados, estrategia de release/rollback, observabilidad de la
plataforma y un ensayo reproducible de restauracion.
