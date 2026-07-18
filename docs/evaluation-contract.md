# Contrato de evaluacion RAG

## Objetivo

La calidad se decide con un dataset versionado, no escogiendo manualmente preguntas que funcionan.
`fde-rag-eval` ingiere el manifiesto sintetico, ejecuta todos los casos y devuelve codigo distinto de
cero si falla una puerta.

## Entradas versionadas

- `examples/knowledge/phase4-documents.json`: 13 documentos con metadata, permisos, hechos
  verificables, dos fuentes restringidas y una instruccion maliciosa.
- `examples/evals/phase4-cases.jsonl`: 38 casos identificados; 32 esperan respuesta y 6 esperan
  rechazo, incluidos tres intentos de consultar fuentes sin permiso.
- El reporte registra SHA-256 de ambas entradas para detectar cualquier cambio.

## Comparacion

- Linea base: recuperacion lexical, un resultado.
- Flujo mejorado: recuperacion hibrida, tres resultados, umbral de evidencia, respuesta extractiva,
  citas verificadas y rechazo.
- El adaptador determinista produce cero tokens y costo cero porque no llama un modelo. Estos ceros
  son mediciones reales del adaptador local, no una estimacion del costo de OpenAI.

## Metricas

- Recall de recuperacion: porcentaje de casos positivos que contienen la fuente esperada.
- Precision de recuperacion: fuentes esperadas divididas entre todos los candidatos `top-3`.
- Exactitud: respuesta aprobada que contiene todos los terminos esperados.
- Groundedness: cada cita pertenece a la fuente esperada del caso.
- Exactitud de rechazo: preguntas negativas rechazadas sin citas.
- Fuga de permiso: aparicion de una fuente restringida en recuperacion o citas.
- Latencia p95: tiempo local observado; no representa una red o un proveedor real.
- Tokens y costo: suma reportada por el proveedor seleccionado.

## Puertas

- Al menos 30 casos.
- Recall mejorado no inferior a la linea base.
- Exactitud de respuesta >= 85%.
- Groundedness >= 95%.
- Exactitud de rechazo >= 95%.
- Cero fugas de permisos.

El criterio de recall acepta empate para no declarar una mejora que el dataset no demuestra. El
reporte actual empata `1.0` contra `1.0`; las mejoras medidas son exactitud, citas, rechazo y control
de permisos. La precision `0.3333` es el resultado esperado de una fuente relevante dentro de tres
candidatos y se conserva para que el cliente pueda optimizarla con datos reales.

## Reproducir

Con PostgreSQL desechable migrado y configuracion de test:

```bash
APP_ENV=test uv run fde-rag-eval \
  --json-output docs/evals/phase4-results.json \
  --markdown-output docs/evals/phase4-results.md
```

El sembrado esta bloqueado fuera de `development` o `test`. Reutiliza documentos identicos mediante
hash y no trunca tablas de un cliente.

## Limite de validez

El resultado local demuestra reproducibilidad de contratos y controles. No demuestra la calidad,
latencia, tokens ni costo de OpenAI. Antes de un piloto deben añadirse casos aprobados por el cliente
y ejecutar el mismo evaluador con los adaptadores reales.
