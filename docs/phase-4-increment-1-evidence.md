# Evidencia — Fase 4, Incremento 1: base LLM controlada

Fecha: 18 de julio de 2026.

## Decision

**Incremento 1 aprobado localmente.** El adaptador real de OpenAI existe, pero no se ejecuto una
solicitud pagada porque la sesion no tenia `OPENAI_API_KEY` ni `OPENAI_API_KEY_FILE`. Esa ausencia no
se oculto: la integracion se valido con un doble determinista y la prueba viva queda como limite
explicito, no como resultado inventado.

Esto no aprueba la Fase 4 completa.

## Evidencia observada

- Resolucion oficial de modelo para trabajo nuevo: `gpt-5.6-sol`.
- SDK bloqueado por lock: `openai==2.46.0`.
- Responses API con `text_format=QueryPlan`, `store=False` y metadata sin contenido.
- Contrato Pydantic estricto para plan, consumo y traza.
- Clave directa o montada mediante `_FILE`; limites de timeout, reintentos y tokens validados.
- Costos desconocidos cuando faltan precios; calculo decimal cuando ambos estan configurados.
- Errores de configuracion, rechazo y proveedor mapeados a respuestas seguras.
- Evento JSON sin pregunta, respuesta ni clave.
- Endpoint autenticado incorporado a OpenAPI versionado.

## Comandos y resultados

```text
uv run ruff check src tests scripts
All checks passed!

uv run ruff format --check src tests scripts
41 files already formatted

uv run mypy src tests scripts
Success: no issues found in 41 source files

TEST_DATABASE_URL=... uv run pytest --cov=fde_foundation --cov-fail-under=75
83 passed
Cobertura total: 76.27%

docker build --pull=false --tag cdf-phase4-inc1:test .
Imagen: sha256:ffbbd317d47b62c1bc86dc8ac53ad85f38aedb16fe4f8f32a17ebb7bfd191c2f

docker run --rm --read-only --cap-drop ALL --security-opt no-new-privileges ...
Usuario: 10001:10001
openai=2.46.0 schema=QueryPlan
```

La primera resolucion remota del frontend Docker y la imagen Python quedo detenida antes de ejecutar
el build. Se cancelo, se reutilizaron localmente los mismos digests fijados y la compilacion aprobo.
No se cambio el Dockerfile ni se sustituyo una imagen base.

## Casos nuevos defendibles

1. El adaptador envia la pregunta como `input`, no dentro de instrucciones.
2. La salida valida contra `QueryPlan` y una salida no parseable falla cerrada.
3. Una negativa del modelo se diferencia de una caida del proveedor.
4. El endpoint exige JWT y devuelve estructura estable.
5. La traza registra tokens, latencia, modelo y prompt sin copiar la pregunta.
6. El costo no aparece como cero cuando en realidad se desconoce.
7. Una clave montada en archivo se acepta sin imprimir su valor.

## Limites

- No hubo llamada real al proveedor por ausencia de credencial en la sesion.
- La clasificacion aun no tiene evaluacion de exactitud con casos reales.
- No existen todavia documentos, embeddings, permisos por documento ni RAG.
- La telemetria es un evento local; persistencia y dashboard llegan en incrementos posteriores.

## Que sigue

**Incremento 2 — recuperacion empresarial:** crear el modelo de documentos y permisos, habilitar
`pgvector`, implementar chunking con metadata y comparar recuperacion semantica, lexical e hibrida.
