# Evidencia de Fase 2 — Incremento 3: contenedores

Fecha: 18 de julio de 2026.

## Alcance aprobado

- Imagen multi-stage reproducible con versiones y digests fijados.
- Ejecucion no-root y filesystem de solo lectura.
- Migracion separada y obligatoria antes del arranque.
- Health check de readiness, recursos limitados y configuracion externa.
- Smoke test HTTP desde otro contenedor y apagado ordenado.

## Evidencia local actual

- `docker build --check .`: sin advertencias.
- Imagen `customer-data-foundation-api:local`: construida correctamente.
- API observada con usuario `10001:10001`, UID real `10001`, root read-only,
  `cap_drop=["ALL"]` y health `healthy`.
- Smoke client aislado: `status=imported`, un registro sintetico y ninguna PII en respuesta.
- `SIGTERM`: `exit_code=0`, `OOMKilled=false` dentro de 15 segundos.
- Migracion con credencial invalida: `api_migrate exit=1`, Compose exit 1 y API no iniciada.
- Suite local: formato y lint aprobados; 40 pruebas aprobadas.

La primera prueba con un init intermediario produjo exit 143. Se retiro porque esta API no
crea procesos hijos; Uvicorn paso a recibir `SIGTERM` directamente como PID 1 y la repeticion
termino con codigo 0. Este hallazgo demuestra por que el apagado se observa y no se asume.

## Pendiente antes del cierre

- Repetir construccion, stack, smoke test y 40 pruebas desde un clon limpio.
- Publicar los cambios y confirmar los jobs `quality` y `container` en GitHub Actions.
