# Guion de demo — Fase 4

## Objetivo para el cliente

Demostrar en menos de diez minutos que el asistente encuentra informacion permitida, muestra de
donde la obtuvo, se niega cuando no sabe y prepara una accion sin ejecutarla hasta que otra persona
la aprueba.

## Preparacion local

```bash
cp .env.example .env
docker compose --profile api up --build -d --wait api
```

Generar tokens breves sin guardarlos en archivos o logs:

```bash
operator_token="$(docker compose exec -T api \
  fde-dev-token --subject demo-operator --role operator)"
auditor_token="$(docker compose exec -T api \
  fde-dev-token --subject demo-auditor --role auditor)"
```

Estos tokens solo funcionan con `APP_ENV=development` y no representan un login de produccion.

## Historia 1 — respuesta con fuente

1. Ingerir un documento con `POST /v1/knowledge/documents` como operador.
2. Preguntar el hecho con `POST /v1/assistant/answers`.
3. Mostrar `status=answered`, el texto y `citations[].source_uri`.
4. Repetir la misma pregunta y mostrar `trace.cached=true`.
5. Explicar que el cache vuelve a comprobar el permiso antes de responder.

Frase para el cliente: “La respuesta no es solo texto convincente; incluye el registro exacto que
la respalda y el sistema verifica esa referencia fuera del modelo.”

## Historia 2 — rechazo seguro

1. Preguntar por una politica inexistente.
2. Mostrar `status=refused`, el mensaje estable y una lista de citas vacia.
3. Consultar un documento asignado a otra identidad y obtener el mismo rechazo sin revelar que la
   fuente existe.

Frase para el cliente: “Cuando no puede demostrarlo con informacion permitida, no adivina.”

## Historia 3 — aprobacion humana

1. Proponer una accion con `POST /v1/assistant/action-plans` y mostrar `pending`.
2. Intentar `POST /v1/actions/{id}/execute` antes de aprobar y mostrar HTTP 409.
3. Intentar aprobar con el mismo sujeto y mostrar HTTP 409.
4. Aprobar con el token del auditor distinto.
5. Ejecutar con el operador y mostrar `simulated_followup_queued`.
6. Ejecutar otra vez y comprobar que no aparece un segundo evento.

Frase para el cliente: “La IA redacta la orden; una persona distinta firma exactamente esos
argumentos; la aplicacion, no el modelo, decide si puede ejecutarse.”

## Historia 4 — evidencia cuantitativa

```bash
APP_ENV=test uv run fde-rag-eval \
  --json-output /tmp/phase4-results.json \
  --markdown-output /tmp/phase4-results.md
```

Mostrar 38 casos, los hashes del dataset, seis puertas en PASS y cero fugas. Aclarar que el proveedor
local no es IA: tokens y costo cero pertenecen solo a esa corrida reproducible.

## Cierre y limpieza

```bash
docker compose stop -t 15 api
docker compose --profile api down --volumes --remove-orphans
```

No usar `down --volumes` sobre un proyecto o volumen de cliente. Este comando pertenece unicamente al
ambiente desechable de la demo.

## Que sigue

**Fase 5:** convertir este backend verificable en una plataforma operable por usuarios reales:
interfaz web, identidad empresarial, despliegue cloud, telemetria de producto y piloto con datos y
casos aprobados por el cliente.
