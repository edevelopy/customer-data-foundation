# Evidencia de Fase 2 — Incremento 5: integracion empresarial

Fecha: 18 de julio de 2026.

## Alcance aprobado

- Segunda API simulada con webhook firmado e idempotente.
- Transactional outbox y worker independiente.
- Timeout, lease, backoff exponencial, presupuesto de reintentos y dead letter.
- Diagnostico autorizado sin PII.
- Pruebas de contrato, concurrencia, fencing y fallos parciales.

## Evidencia observada

- Migracion `0004_integration_outbox` aplicada en PostgreSQL de pruebas y desarrollo.
- Formato, lint y configuracion Compose aprobados.
- 52 pruebas aprobadas, incluida la transicion a `dead_letter`, payload estricto y contrato de
  endurecimiento de los servicios.
- Imagen multi-stage reconstruida sin advertencias.
- `api`, `partner_api` e `integration_worker` saludables como procesos separados.
- Smoke HTTP real: primer intento `partner_http_503`, segundo intento `delivered`.
- El mismo evento termino con `attempt_count=2`; el resultado no expuso email ni telefono.
- Los tres procesos ejecutaron como `10001:10001`, root filesystem read-only y `cap_drop=ALL`.
- Trivy encontro cero vulnerabilidades corregibles `HIGH` o `CRITICAL`.
- API, partner y worker terminaron con codigo `0` dentro de 15 segundos.
- Commit funcional: `51e5cfedf25163e068742938839dbe9bd23f3ddb`.
- Pipeline remoto [CI 29635699407](https://github.com/edevelopy/customer-data-foundation/actions/runs/29635699407):
  `quality`, `container`, `image_changes` y `publish` aprobados.
- El job `container` reconstruyo desde un checkout limpio y observo el recorrido
  `503 -> backoff -> delivered`, el aislamiento y el apagado ordenado.
- Imagen publica multi-plataforma (`linux/amd64` y `linux/arm64`):
  `ghcr.io/edevelopy/customer-data-foundation-api@sha256:092ffa1becb253868beae5bc5a66fbfd06177393ce7eef846c3051d1934db579`.
- Pull anonimo por digest aprobado; la variante `linux/amd64` conserva
  `User=10001:10001`.
- Trivy remoto encontro cero vulnerabilidades corregibles `HIGH` o `CRITICAL`.
- SBOM `SPDX-2.3`: 137 paquetes; SHA-256
  `4c45c8e25240062a729c2c32553dd8be8d2938396b31f32d600378f1f66f0076`.
- Provenance SLSA y attestation SPDX verificadas contra el workflow del repositorio.

El incremento queda cerrado por comportamiento observado local y remotamente, no solo por la
existencia del codigo.

## Limites

El socio comparte PostgreSQL exclusivamente en la simulacion local. El payload no replica perfiles
de clientes. No existe todavia broker administrado, alerta de backlog, UI de replay ni despliegue
cloud. El incremento tampoco constituye la evaluacion final de la Fase 2.
