# Evidencia de Fase 2 — Incremento 1: contrato HTTP

Fecha: 18 de julio de 2026.

## Alcance aprobado

- API sincrona con FastAPI.
- `POST /v1/imports`, `GET /v1/imports/{operation_id}` y health checks separados.
- Operador envia y consulta lo propio; auditor consulta cualquier operacion.
- JWT obligatorio, clave de idempotencia obligatoria y limites de 10 MiB/10,000 filas.
- Ningun listado de clientes y ninguna PII en respuestas o logs operacionales.

## Evidencia automatizada local

Comandos:

```bash
uv run ruff format --check .
uv run ruff check .
TEST_DATABASE_URL=postgresql://fde_test:***@localhost:55434/fde_test uv run pytest
```

Resultado observado: 33 pruebas aprobadas, incluyendo PostgreSQL real para integracion.

Casos cubiertos:

- Importacion valida y lectura con control de propietario.
- Lectura global por auditor y rechazo de escritura para auditor.
- Credencial ausente, vencida o con audiencia incorrecta.
- Reintento exacto y dos reservas simultaneas con una unica operacion.
- Reutilizacion de la clave para otro contenido.
- Persistencia de sujeto y clave como HMAC, sin los valores originales.
- Archivo invalido sin PII, header ausente y archivo mayor de 10 MiB.
- Liveness, readiness, migraciones, transacciones, rollback y concurrencia del importador.

## Evidencia contra el proceso HTTP real

Se inicio `fde-api` en `127.0.0.1:8000` y se uso `curl`, fuera del proceso, con credenciales
locales de corta duracion. Resultado observado:

- `/health/live` devolvio `{"status":"ok"}`.
- `/health/ready` devolvio `{"status":"ready"}`.
- La importacion devolvio `status=imported` y `operation_id=95cfe24f-467e-4431-8218-7f0277cb0a91`.
- El reintento exacto devolvio una respuesta identica y el mismo `operation_id`.
- El auditor leyo esa operacion y su intento de importar devolvio HTTP `403`.
- El archivo invalido devolvio `validation_failed`, tres tipos de error y cero PII.
- Los tres eventos emitidos conservaron exclusivamente los campos aprobados.

## Estado del entregable

Este documento registra un incremento verificable, no la evaluacion final de Fase 2. Antes de
aprobar la fase completa faltan verificacion desde clon limpio, CI remoto y una simulacion de
interrupcion/recuperacion documentada.
