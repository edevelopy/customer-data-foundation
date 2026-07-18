# Evidencia de Fase 2 — Incremento 5: integracion empresarial

Fecha: 18 de julio de 2026.

## Alcance aprobado

- Segunda API simulada con webhook firmado e idempotente.
- Transactional outbox y worker independiente.
- Timeout, lease, backoff exponencial, presupuesto de reintentos y dead letter.
- Diagnostico autorizado sin PII.
- Pruebas de contrato, concurrencia, fencing y fallos parciales.

## Evidencia local observada

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

La evidencia remota, el conteo final de pruebas, el escaneo de imagen y el pipeline se completan
despues del primer push. Este documento no cierra el incremento solo porque el codigo exista.

## Limites

El socio comparte PostgreSQL exclusivamente en la simulacion local. El payload no replica perfiles
de clientes. No existe todavia broker administrado, alerta de backlog, UI de replay ni despliegue
cloud. El incremento tampoco constituye la evaluacion final de la Fase 2.
