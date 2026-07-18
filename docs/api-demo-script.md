# Guion de demo — API empresarial del importador

Duracion objetivo: seis minutos. Usar solamente los CSV sinteticos de `examples/`.

## 1. Lenguaje para cliente no tecnico — 45 segundos

> Convertimos el importador en un servicio controlado. Otro sistema puede enviar el archivo,
> pero solo con permiso; recibe un numero de seguimiento y un resultado sin datos personales.
> Si repite accidentalmente la solicitud, no duplica el trabajo.

## 2. Preparacion local — 60 segundos

```bash
set -a
source .env
set +a
docker compose up -d --wait database
uv run alembic upgrade head
uv run fde-api
```

En otra terminal, generar una credencial local de 15 minutos. No copiarla a documentos, logs
o control de versiones:

```bash
set -a
source .env
set +a
OPERATOR_TOKEN=$(uv run fde-dev-token --subject operator-demo --role operator)
```

## 3. Salud e importacion — 90 segundos

```bash
curl --fail http://127.0.0.1:8000/health/live
curl --fail http://127.0.0.1:8000/health/ready
curl --silent --show-error \
  -H "Authorization: Bearer $OPERATOR_TOKEN" \
  -H "Idempotency-Key: demo-import-0001" \
  -F "file=@examples/customers-valid.csv;type=text/csv" \
  http://127.0.0.1:8000/v1/imports
```

Mostrar `operation_id`, estado y conteos. No mostrar la credencial.

## 4. Reintento seguro — 45 segundos

Repetir exactamente el ultimo `curl`. Debe devolver el mismo `operation_id` y la misma
respuesta. Explicar que la clave evita duplicar una operacion si la red o el sistema llamador
reintentan.

## 5. Separacion de permisos — 60 segundos

Crear una credencial `auditor`, consultar el `operation_id` y mostrar que puede revisar el
resultado. Intentar enviar un archivo con esa credencial y comprobar `403`.

## 6. Fallo seguro — 60 segundos

Enviar `examples/customers-invalid.csv` con una clave nueva. Mostrar `422`, fila, campo y
correccion; confirmar que la respuesta no copia email ni telefono.

## 7. Limites honestos — 30 segundos

Explicar que este es el primer incremento de Fase 2: funciona localmente y tiene contrato,
autorizacion y pruebas, pero todavia no es un despliegue productivo ni el examen final.
