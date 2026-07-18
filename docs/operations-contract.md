# Contrato de metricas y alertas operacionales

## Objetivo

El operador debe poder responder tres preguntas sin consultar datos de clientes: si la API esta
lista, si existen trabajos abandonados y si la entrega al socio esta atrasada o agotada.

`GET /metrics` publica formato Prometheus y exige un Bearer token dedicado, distinto del JWT de
usuarios. `fde-ops-check` produce el mismo snapshot como JSON y devuelve codigo `1` cuando existe
una alerta. Ambos leen conteos agregados; no emiten nombres, emails, telefonos, hashes de actores,
payloads, URLs ni secretos.

## Metricas estables

- `fde_imports_total`, `fde_imports_processing` y `fde_imports_failed`.
- `fde_imports_expired_processing`: leases vencidos que requieren recuperacion.
- `fde_outbox_pending`, `fde_outbox_delivering`, `fde_outbox_delivered`.
- `fde_outbox_dead_letter`: eventos agotados que requieren intervencion.
- `fde_outbox_oldest_pending_seconds`: edad del evento no entregado mas antiguo.

El archivo [`deploy/prometheus-alerts.yml`](../deploy/prometheus-alerts.yml) materializa tres reglas:
lease vencido y dead letter son criticos; una entrega pendiente durante cinco minutos es warning.
Antes de usar otro SLO, el cliente debe aprobar el umbral y su canal de escalamiento.

## Uso seguro

```bash
DATABASE_URL_FILE=/run/secrets/database_url uv run fde-ops-check
curl --fail --header "Authorization: Bearer $METRICS_TOKEN" http://127.0.0.1:8080/metrics
```

No copies el token en historiales o capturas. En una plataforma compartida, el scraper obtiene el
token de su gestor de secretos, usa TLS y accede a `/metrics` por una red privada. El piloto entrega
reglas y evaluacion, pero no presupone PagerDuty, Slack ni otro canal comercial.

## Observabilidad de plataforma

Compose agrega healthchecks, politica de reinicio y limites de CPU, memoria y PIDs. La API es la
unica entrada publicada; PostgreSQL, partner y worker permanecen en la red interna. El estado de
contenedores y los logs JSON tecnicos completan las metricas de aplicacion.
