# Contrato de integracion — evento de importacion completada

## Semantica

La entrega es **at-least-once**. El emisor puede enviar el mismo evento mas de una vez; el receptor
debe deduplicar por `event_id`. No se promete exactly-once entre dos bases independientes.

El outbox se inserta en la transaccion que marca la operacion HTTP como terminada. Una operacion
aceptada tiene como maximo un evento por la restriccion unica de `operation_id`.

## Endpoint socio

```text
POST /partner/v1/import-events
Content-Type: application/json
Idempotency-Key: <event_id>
X-FDE-Event-Id: <event_id>
X-FDE-Timestamp: <segundos Unix>
X-FDE-Signature: v1=<HMAC-SHA256>
```

La firma se calcula sobre los bytes exactos:

```text
HMAC-SHA256(secret, timestamp + "." + body)
```

El receptor usa comparacion constante, exige que los dos headers de identidad y el body tengan el
mismo UUID y rechaza timestamps con mas de cinco minutos de diferencia.

## Payload `1.0`

```json
{
  "event_id": "0d370f45-3556-4a31-9f78-418675ef39ee",
  "event_type": "customer_import.completed",
  "existing_rows": 1,
  "inserted_rows": 2,
  "occurred_at": "2026-07-18T07:20:00+00:00",
  "operation_id": "7f852649-b5a2-4ec4-84b2-89a713c398ac",
  "schema_version": "1.0",
  "status": "imported",
  "total_rows": 3
}
```

Campos adicionales se rechazan; no se ignoran silenciosamente. Ningun campo identifica una
persona y el body completo tiene un limite de 16 KiB.

## Respuestas e idempotencia

- `200`: aceptado; una repeticion exacta tambien devuelve `200` con `duplicate=true`.
- `400`: headers o timestamp mal formados; no reintentar sin corregir el emisor.
- `401`: firma invalida o vencida; no reintentar automaticamente.
- `409`: identidad inconsistente o mismo `event_id` con otro body; no reintentar.
- `413`: body superior a 16 KiB; no reintentar sin corregir el emisor.
- `422`: version, tipo o payload no soportado; no reintentar.
- `408`, `425`, `429` y `5xx`: fallo temporal; aplicar backoff.
- timeout o error de red: fallo temporal; aplicar backoff.

## Estados y recuperacion

```text
pending -> delivering -> delivered
   ^            |
   |            +-> pending (fallo temporal + backoff)
   |            +-> dead_letter (permanente o presupuesto agotado)
   +------------+ (lease vencido; otro worker recupera)
```

El intento 1 espera 1 segundo; luego 2, 4, 8 y hasta un maximo configurable de 30 segundos en el
piloto. El quinto fallo termina en `dead_letter`. Cada reserva incrementa `attempt_count`; un worker
viejo no puede completar el intento nuevo porque las escrituras usan ese contador como fencing
token. `FOR UPDATE SKIP LOCKED` permite varios workers sin asignar el mismo evento activo.

## Diagnostico desde la API principal

`GET /v1/integrations/{operation_id}` aplica la misma visibilidad que la importacion: el operador
solo ve la propia y el auditor puede ver cualquiera. Devuelve:

- `event_id`, `operation_id` y `event_type`;
- `status`, `attempt_count` y `available_at`;
- `last_failure_code` y `delivered_at`.

No devuelve el payload, firma, secreto ni URL del socio.
