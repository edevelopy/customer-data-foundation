# Evidencia — Fase 4, Incremento 5: agente controlado

Fecha: 18 de julio de 2026.

## Decision

**Incremento 5 aprobado localmente.** El agente propone una unica accion simulada con esquema
estricto, pero no puede ejecutarla sin aprobacion vinculada de un auditor diferente. Esta aprobacion
cierra los incrementos funcionales; falta la evaluacion final de la Fase 4 desde un clon limpio.

## Evidencia observada

- Funcion `send_customer_followup` con tres argumentos cerrados y sin texto libre.
- Adaptador Responses API con tool schema estricto, sin llamadas paralelas y `store=False`.
- El planificador no contiene codigo de ejecucion de la herramienta.
- Estado persistente `pending -> approved -> executed` protegido con transacciones y bloqueo de fila.
- Autoaprobacion y ejecucion anticipada bloqueadas.
- Reejecucion idempotente; un solo evento `executed`.
- Auditoria append-only con hashes de actor y argumentos.
- Rate limit antes del planificador y limites RAG por solicitud y tokens diarios.
- Cache separado por sujeto, con TTL y revalidacion de permisos de cada cita.
- Fallback extractivo marcado `degraded`, nunca confundido con respuesta del proveedor.

## Comandos y resultados

```text
uv run ruff format --check .
61 files already formatted

uv run ruff check .
All checks passed!

uv run mypy src tests scripts
Success: no issues found in 53 source files

TEST_DATABASE_URL=... PHASE4_TEST_DATABASE_URL=... \
  uv run pytest --cov=fde_foundation --cov-branch --cov-report=term-missing \
  --cov-fail-under=75
109 passed in 27.79s
Cobertura total: 78.44%
```

## Casos defendibles

1. Ejecutar una solicitud pendiente devuelve conflicto.
2. El mismo sujeto no puede solicitar y aprobar.
3. Un auditor distinto aprueba exactamente el hash de argumentos propuesto.
4. La ejecucion simulada ocurre una vez y el replay es idempotente.
5. El rate limit bloquea antes de otra planificacion.
6. El adaptador OpenAI expone una sola herramienta estricta y no la ejecuta.
7. Una respuesta cacheada evita otra generacion.
8. Revocar permisos impide reutilizar una cita cacheada.
9. Presupuesto y limite de solicitudes detienen el flujo con fallo controlado.
10. Una caida del proveedor produce `degraded` solo cuando existe evidencia autorizada.

## Limites honestos

- No se envio una accion real ni se conecto correo o CRM.
- No hubo una llamada pagada a OpenAI; tool calling se valido con un doble de contrato.
- Los valores de limites son defaults de plantilla, no una politica aprobada por un cliente.
- El cache guarda respuestas; produccion exige cifrado, retencion y borrado aprobados.

## Que sigue

**Evaluacion final de la Fase 4:** matriz completa de requisitos, migracion y rollback, seguridad,
contenedor, demo, clon limpio, PR, CI, merge, `main` verde e imagen publicada por digest.
