# Plan de entrega — Fase 4: IA aplicada y verificable

Fecha de inicio: 18 de julio de 2026.

## Resultado esperado

El proyecto evolucionara de una integracion de datos a un asistente RAG empresarial. No se aprobara
por parecer inteligente en una demo: debera recuperar evidencia autorizada, citarla, abstenerse sin
soporte y superar un conjunto reproducible de al menos 30 casos.

## Incrementos

| Incremento | Entrega verificable | Puerta de salida |
|---|---|---|
| 1. Base LLM | Responses API, salida estructurada, prompt/model versionados y tokens/latencia/costo | Adaptador simulado, contrato HTTP y regresion completa aprobados |
| 2. Recuperacion | Documentos, chunking, metadata, permisos, `pgvector` y busqueda hibrida | Un usuario solo recupera fragmentos autorizados y relevantes |
| 3. RAG seguro | Respuestas con fuentes, umbral de evidencia y defensa contra prompt injection | Cita correcta o rechazo seguro; nunca obedece instrucciones del documento |
| 4. Evaluacion | Al menos 30 casos, linea base vs mejora, groundedness, latencia, costo y rechazo | Resultados reproducibles y mejora medida, no seleccion manual |
| 5. Agente controlado | Tool calling, accion simulada, aprobacion humana, auditoria, limites y degradacion | Ninguna accion sensible ocurre sin aprobacion explicita vinculada |

Despues se realizara una evaluacion final de la Fase 4 con evidencia desde un clon limpio.

## Decisiones iniciales

- Python continua como lenguaje principal.
- Se usa la Responses API para trabajo nuevo y Pydantic para evitar divergencia entre esquema y tipo.
- El modelo inicial configurable es `gpt-5.6-sol`; el nombre no queda disperso por el codigo.
- `store=False` evita almacenamiento del lado del proveedor para este flujo.
- Las preguntas se tratan como contenido no confiable y nunca se mezclan con instrucciones.
- Los precios no se fijan en codigo: se configuran externamente y, si faltan, el costo es desconocido.
- La clave admite `OPENAI_API_KEY_FILE`; no pertenece a Git, imagen, logs ni respuesta HTTP.
- Cada resultado expone version del prompt, modelo, tokens, latencia y costo estimado, sin exponer la
  pregunta en la traza.

## Estado actual

- Incremento 1: aprobado localmente; frontera LLM estructurada y observable.
- Incremento 2: aprobado localmente; documentos versionados, pgvector, permisos y recuperacion
  hibrida.
- Incremento 3: aprobado localmente; respuestas fundamentadas, citas y rechazo seguro.
- Incremento 4: en construccion; evaluacion reproducible de al menos 30 casos.

La ausencia de una credencial de OpenAI se registra como limite: los adaptadores reales existen,
pero las pruebas locales deterministas no se presentan como llamadas ni calidad real del proveedor.
