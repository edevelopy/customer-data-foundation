# Evidencia — Fase 4, Incremento 4: evaluacion reproducible

Fecha: 18 de julio de 2026.

## Decision

**Incremento 4 aprobado localmente.** Los 38 casos versionados superan las seis puertas de aceptacion
con el adaptador determinista. La aprobacion cubre reproducibilidad y controles; no se presenta como
una evaluacion viva de OpenAI.

## Resultado observado

| Metrica | Resultado |
|---|---:|
| Casos | 38 |
| Positivos / negativos | 32 / 6 |
| Recall linea base | 1.0 |
| Recall mejorado | 1.0 |
| Precision hibrida top-3 | 0.3333 |
| Exactitud de respuesta | 1.0 |
| Groundedness | 1.0 |
| Exactitud de rechazo | 1.0 |
| Fugas de permisos | 0 |
| Latencia p95 baseline / flujo completo | 37 ms / 109 ms |
| Tokens / costo local | 0 / USD 0.0 |

Los tiempos pertenecen a la corrida versionada en
[`docs/evals/phase4-results.json`](evals/phase4-results.json) y pueden variar entre maquinas. Los
hashes de documentos y casos estan incluidos en ese mismo artefacto.

## Interpretacion honesta

- El recall mejorado empata, no supera, la linea base. No se afirma una mejora de recall.
- La precision de `0.3333` refleja una fuente relevante entre tres candidatos. Es visible y queda
  como objetivo de optimizacion con datos representativos.
- El flujo completo añade una segunda recuperacion, generacion, verificacion y traza; por eso es mas
  lento que la linea base local.
- Exactitud, groundedness y rechazo alcanzan 1.0 en datos sinteticos. Eso prueba el comportamiento
  determinista de esta version, no generalizacion a documentos reales.
- Cero tokens y costo significan que el adaptador local no usa IA; no son el costo esperado de
  `gpt-5.6-sol`.

## Verificacion de software

```text
uv run ruff format --check .
57 files already formatted

uv run ruff check .
All checks passed!

uv run mypy src tests scripts
Success: no issues found in 50 source files

TEST_DATABASE_URL=... PHASE4_TEST_DATABASE_URL=... \
  uv run pytest --cov=fde_foundation --cov-branch --cov-report=term-missing \
  --cov-fail-under=75
103 passed in 26.33s
Cobertura total: 78.25%
```

## Que sigue

**Incremento 5 — agente controlado:** añadir tool calling con esquema estricto, solicitud de accion
simulada, aprobacion humana separada, auditoria, rate limit, presupuesto, cache y degradacion segura.
