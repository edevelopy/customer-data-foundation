# Evidencia — Fase 4, Incremento 3: RAG seguro

Fecha: 18 de julio de 2026.

## Decision

**Incremento 3 aprobado localmente.** El endpoint autenticado entrega una respuesta con fuentes solo
cuando existe evidencia autorizada suficiente y bloquea citas inventadas. Esto no aprueba todavia la
calidad estadistica del asistente ni la Fase 4 completa.

## Evidencia observada

- `POST /v1/assistant/answers` incorporado al contrato OpenAPI versionado.
- Recuperacion hibrida con señales lexicales y similitud coseno explicitas.
- Rechazo antes de invocar el generador cuando no existe evidencia suficiente.
- Verificacion posterior al proveedor: cada cita debe ser un fragmento recuperado y autorizado.
- Prompt de OpenAI separa instrucciones de pregunta y documentos no confiables.
- Responses API con Pydantic, `store=False`, prompt versionado y metadata sin contenido.
- Trazas persistentes con hashes y metricas, sin columnas de pregunta, respuesta, sujeto o contenido.
- Adaptador local reproducible identificado explicitamente como no-IA.

## Pruebas de seguridad nuevas

1. Un usuario autorizado recibe la respuesta y una cita verificable.
2. Un usuario sin permiso recibe rechazo aunque el documento exista.
3. Una pregunta irrelevante recibe rechazo y cero citas.
4. Una instruccion maliciosa dentro del documento no controla la salida.
5. Un proveedor que inventa un UUID de cita falla cerrado.
6. La respuesta HTTP exige JWT y no expone el contenido dentro de la cita.
7. La traza contiene hashes y conteos, pero no los textos sensibles.
8. El adaptador OpenAI envia salida estructurada y desactiva almacenamiento.

## Comandos y resultados

```text
uv run ruff format --check .
55 files already formatted

uv run ruff check .
All checks passed!

uv run mypy src tests scripts
Success: no issues found in 48 source files

TEST_DATABASE_URL=... PHASE4_TEST_DATABASE_URL=... \
  uv run pytest --cov=fde_foundation --cov-branch --cov-report=term-missing \
  --cov-fail-under=75
101 passed in 11.68s
Cobertura total: 78.19%
```

## Limites honestos

- No hubo llamada real a OpenAI por ausencia de credencial; no se inventaron respuesta, tokens ni
  costo del proveedor.
- El caso local prueba controles y contratos, no la calidad de `gpt-5.6-sol`.
- El umbral `0.20` es inicial. Su comportamiento cuantitativo se medira en el siguiente incremento.
- Cache, presupuesto, rate limit y degradacion controlada llegan en el Incremento 5.

## Que sigue

**Incremento 4 — evaluacion reproducible:** crear al menos 30 casos versionados, comparar una linea
base contra el flujo mejorado y medir recuperacion, exactitud, groundedness, rechazo, permisos,
latencia, tokens y costo sin seleccionar resultados manualmente.
