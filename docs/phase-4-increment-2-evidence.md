# Evidencia — Fase 4, Incremento 2: recuperacion empresarial

Fecha: 18 de julio de 2026.

## Decision

**Incremento 2 aprobado localmente.** La aplicacion ya ingiere documentos versionados y recupera
fragmentos autorizados mediante busqueda lexical, vectorial o hibrida. Esto aprueba la frontera de
recuperacion, no la calidad final del asistente ni la Fase 4 completa.

## Evidencia observada

- PostgreSQL con pgvector en `pgvector/pgvector:pg18-trixie`; los ambientes de Compose fijan el
  digest multi-plataforma `sha256:9d2e61c7352b9e9f4798df5fd9a498f043f4cda1cdacc707de3d198650f4321e`.
- Migracion `0005_enterprise_knowledge` con documentos, versiones, permisos, fragmentos, GIN y HNSW.
- Chunking acotado, solapado y determinista; hashes de contenido e idempotencia comprobados.
- Permisos aplicados en SQL mediante el hash del sujeto autenticado.
- Filtros de metadata y los tres modos de recuperacion probados contra PostgreSQL real.
- Adaptadores de embeddings local determinista y OpenAI con dimensiones configuradas.
- Contratos HTTP incorporados al OpenAPI versionado.

## Comandos y resultados

```text
uv run ruff check src tests scripts
All checks passed!

uv run ruff format --check src tests scripts
45 files already formatted

uv run mypy src tests scripts
Success: no issues found in 45 source files

TEST_DATABASE_URL=... PHASE4_TEST_DATABASE_URL=... \
  uv run pytest --cov=fde_foundation --cov-branch --cov-report=term-missing \
  --cov-fail-under=75
94 passed in 10.12s
Cobertura total: 77.76%
```

## Casos defendibles

1. Reingestar el mismo documento no crea una version duplicada.
2. Cambiar el contenido crea una version nueva y desactiva la anterior.
3. Un sujeto autorizado recupera los fragmentos correspondientes.
4. Otro sujeto recibe cero fragmentos del mismo documento.
5. El filtro de metadata restringe el conjunto antes del ranking.
6. Los modos lexical, semantico e hibrido respetan la misma frontera de permisos.
7. Los marcadores de instrucciones maliciosas se conservan como señal, no se ejecutan.

## Limites honestos

- No se hizo una llamada pagada a embeddings porque la sesion no dispone de credencial de OpenAI.
- La prueba determinista valida contratos, versionado y aislamiento; no se presenta como evidencia de
  calidad semantica de un modelo.
- Todavia no se generan respuestas ni citas. Ese trabajo pertenece al siguiente incremento.

## Que sigue

**Incremento 3 — RAG seguro:** responder solo con evidencia autorizada, citar la fuente exacta,
rechazar preguntas sin soporte y demostrar que instrucciones incrustadas en documentos no controlan
al asistente.
