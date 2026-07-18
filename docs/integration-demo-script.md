# Demo reproducible — fallo parcial y recuperacion

## Mensaje para audiencia no tecnica

"La importacion del cliente no depende de que el sistema socio este disponible. Guardamos una
notificacion durable, la firmamos y la reintentamos sin duplicarla. Soporte puede ver ambos estados
sin abrir los datos de una persona."

## Preparacion

```bash
cp .env.example .env
docker compose --profile api --profile integration up --build -d --wait \
  api partner_api integration_worker
```

`PARTNER_SIMULATED_FAILURES=1` obliga al socio a responder `503` al primer intento de cada evento.
El smoke client crea una importacion sintetica y espera la recuperacion:

```bash
operator_token="$(docker compose exec -T api \
  fde-dev-token --subject integration-demo --role operator)"
OPERATOR_TOKEN="$operator_token" docker compose \
  --profile api --profile integration --profile integration-smoke \
  run --rm integration_smoke
```

Resultado esperado, con UUID diferentes en cada ejecucion:

```json
{
  "attempt_count": 2,
  "event_id": "...",
  "last_failure_code": "partner_http_503",
  "operation_id": "...",
  "status": "delivered"
}
```

La demostracion no imprime el JWT, secreto HMAC, email, telefono ni body firmado. El agente puede
ejecutar estos comandos durante una entrega; la persona FDE explica el problema, valida el resultado
y decide si los limites corresponden al cliente.
