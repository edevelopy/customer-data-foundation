# Evaluacion final — Fase 4

Fecha: 18 de julio de 2026.

## Veredicto

**Fase 4 aprobada para el alcance tecnico reproducible del repositorio: 91/100.** La version `0.4.0`
entrega recuperacion autorizada, RAG con citas, evaluacion versionada y una accion simulada con
aprobacion humana. No se aprueba todavia un piloto productivo con OpenAI o datos de un cliente.

## Matriz de resultado

| Area | Puntos | Evidencia |
|---|---:|---|
| Recuperacion y permisos | 20/20 | pgvector, versionado, metadata, lexical/semantica/hibrida y permisos en SQL |
| RAG seguro | 19/20 | Umbral, citas verificadas, rechazo, prompt injection, trazas sin contenido y cache revalidado |
| Evaluacion | 17/20 | 38 casos, hashes, baseline y seis puertas; falta dataset real y llamada viva |
| Agente controlado | 20/20 | Tool schema estricto, separacion de aprobacion, auditoria e idempotencia |
| Reproducibilidad y operacion | 15/20 | 109 pruebas, clon limpio, migracion/rollback y contenedor endurecido; falta piloto cloud |
| **Total** | **91/100** | **Aprobada localmente, no equivalente a produccion** |

## Evidencia final observada

- Ciclo completo sobre PostgreSQL/pgvector desechable: `alembic downgrade base` y
  `alembic upgrade head` aprobaron hasta `0007_controlled_actions`.
- Benchmark desde el esquema reconstruido: 38 casos; recall baseline/mejorado `1.0/1.0`, precision
  top-3 `0.3333`, exactitud `1.0`, groundedness `1.0`, rechazo `1.0` y cero fugas.
- Clon limpio: `uv sync --locked`, formato, lint, mypy y 109 pruebas aprobaron; cobertura de ramas
  total `78.44%` contra una puerta de 75%.
- Dockerfile check sin advertencias e imagen local `0.4.0`
  `sha256:6fb1bb57f3faecc9342b28b6b6fd10e99aa570377eb5307f8383404b1cf7d221`.
- Runtime observado: usuario `10001:10001`, raiz de solo lectura, `cap_drop=ALL`, migracion previa a
  readiness y terminacion SIGTERM con codigo cero.
- Smoke RAG: respuesta `answered` con `kb://phase4/smoke`; segunda llamada `cached=true`.
- Smoke agente: `pending -> approved -> executed` con resultado `simulated_followup_queued`.
- El stack, red y volumen de smoke fueron eliminados despues de la prueba.

## Lo que se demostro

1. La autorizacion ocurre antes de la generacion y tambien se revalida al usar cache.
2. La aplicacion bloquea citas fuera de la evidencia aunque el proveedor las produzca.
3. Documentos con instrucciones maliciosas se tratan como datos sin autoridad.
4. La ausencia de evidencia es un rechazo medido, no un error oculto ni una respuesta inventada.
5. El modelo solo puede proponer la unica accion definida; no contiene una ruta de ejecucion directa.
6. Un auditor diferente aprueba el hash exacto y la ejecucion es idempotente.
7. Rate limits, presupuesto, cache y fallback degradado se prueban como controles de software.

## Limites que impiden llamarlo piloto productivo

- La sesion no dispone de `OPENAI_API_KEY`; no hubo llamadas vivas, tokens, costos, latencia ni
  calidad real de `gpt-5.6-sol` o `text-embedding-3-small`.
- El recall mejorado empato la linea base. La precision top-3 es `0.3333`; debe optimizarse con casos
  representativos, no ocultarse.
- Los documentos y 38 casos son sinteticos. Un cliente debe aprobar datos, etiquetas y criterios.
- `send_customer_followup` es una simulacion; no existe integracion real de correo o CRM.
- Los defaults de roles, TTL, limites y presupuesto son plantilla, no politica empresarial.
- Falta interfaz web, proveedor de identidad, despliegue cloud y observabilidad de uso del producto.

## Decision operativa

El codigo puede fusionarse como Fase 4 porque sus afirmaciones locales son reproducibles y sus
limites estan documentados. Un piloto requiere una nueva puerta: credencial administrada, dataset del
cliente, evaluacion viva, threat review, politica de retencion y accion externa en sandbox.

## Que sigue

**Fase 5 — plataforma y piloto real:** interfaz para usuarios no tecnicos, SSO/RBAC empresarial,
despliegue cloud, telemetria de producto, evaluacion con datos aprobados y una integracion externa en
sandbox antes de habilitar cualquier accion productiva.
